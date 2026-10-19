"""Attack source: PyRIT supplies the adversarial phrasings; this module turns the
benign banking objectives (attacks/objectives.yaml) into concrete test cases by
wrapping them in those phrasings.

PyRIT resolution order:
  1. the installed `pyrit` package (pyrit.datasets.TextJailBreak), if importable
  2. the vendored MIT-licensed template copies in attacks/pyrit_vendored/

Either way the jailbreak wrapping comes from PyRIT, not from this project.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from ..config import ATTACKS_DIR

log = logging.getLogger(__name__)

VENDORED = ATTACKS_DIR / "pyrit_vendored"
# Which vendored jailbreak templates to apply (one test case per template).
JAILBREAK_TEMPLATES = ["aim", "dan_1", "better_dan", "aligned", "anti_gpt"]


# --------------------------------------------------------------- PyRIT loading

@lru_cache(maxsize=1)
def pyrit_source() -> str:
    """Report which PyRIT source is in use, for the report's provenance line."""
    try:
        import pyrit  # noqa: F401
        from pyrit.datasets import TextJailBreak  # noqa: F401

        return f"pyrit (installed, v{_pyrit_version()})"
    except Exception:
        return "pyrit (vendored templates, MIT)"


def _pyrit_version() -> str:
    try:
        from importlib.metadata import version

        return version("pyrit")
    except Exception:
        return "unknown"


def _render_with_installed_pyrit(template_name: str, objective: str) -> str | None:
    try:
        from pyrit.datasets import TextJailBreak

        jb = TextJailBreak(template_file_name=f"{template_name}.yaml")
        return jb.get_jailbreak(prompt=objective)
    except Exception as exc:
        log.debug("installed PyRIT render failed for %s: %s", template_name, exc)
        return None


@lru_cache(maxsize=None)
def _vendored_template(template_name: str) -> str:
    path = VENDORED / "jailbreak" / f"{template_name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["value"]


def _render_with_vendored(template_name: str, objective: str) -> str:
    """Vendored PyRIT templates use a {{ prompt }} Jinja slot."""
    tmpl = _vendored_template(template_name)
    if "{{ prompt }}" in tmpl:
        return tmpl.replace("{{ prompt }}", objective)
    if "{{prompt}}" in tmpl:
        return tmpl.replace("{{prompt}}", objective)
    return tmpl.rstrip() + "\n\n" + objective


def wrap_jailbreak(template_name: str, objective: str) -> str:
    return _render_with_installed_pyrit(template_name, objective) or _render_with_vendored(template_name, objective)


@lru_cache(maxsize=1)
def _steal_seeds() -> list[str]:
    path = VENDORED / "seeds" / "psfuzz_steal_system.prompt"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [s["value"].strip() for s in data.get("seeds", []) if s.get("value")]


# ------------------------------------------------------------------ test cases

@dataclass
class TestCase:
    id: str
    module: str
    objective_id: str
    technique: str           # "pyrit:aim", "pyrit:steal_seed", "direct", "multi-turn", "paired"
    severity: str
    owasp: str
    turns: list[str] = field(default_factory=list)
    document: str | None = None
    session: dict = field(default_factory=dict)
    expect: dict = field(default_factory=dict)
    control: bool = False
    pair: list[str] | None = None
    attribute: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _load_objectives() -> dict:
    return yaml.safe_load((ATTACKS_DIR / "objectives.yaml").read_text(encoding="utf-8"))["modules"]


def build_suite(modules: list[str] | None = None, include_controls: bool = True,
                max_jailbreaks: int | None = None) -> list[TestCase]:
    """Expand objectives into the full ordered list of test cases."""
    spec = _load_objectives()
    templates = JAILBREAK_TEMPLATES[:max_jailbreaks] if max_jailbreaks else JAILBREAK_TEMPLATES
    cases: list[TestCase] = []

    for module, mspec in spec.items():
        if modules and module not in modules:
            continue
        sev, owasp = mspec["severity"], mspec.get("owasp", "")
        default_wrap = mspec.get("default_wrap", "none")

        for obj in mspec["objectives"]:
            if obj.get("control") and not include_controls:
                continue
            oid = obj["id"]
            base = dict(module=module, objective_id=oid, severity=sev, owasp=owasp,
                        document=obj.get("document"), session=obj.get("session", {}),
                        expect=obj.get("expect", {}), control=obj.get("control", False),
                        attribute=obj.get("attribute"))

            # Fair-lending pairs: two prompts that must produce matching decisions.
            if obj.get("pair"):
                cases.append(TestCase(id=f"{oid}", technique="paired", turns=list(obj["pair"]),
                                      pair=list(obj["pair"]), **base))
                continue

            # Multi-turn objectives are sent as-is (phrasing is the escalation itself).
            if obj.get("turns"):
                cases.append(TestCase(id=f"{oid}", technique="multi-turn", turns=list(obj["turns"]), **base))
                continue

            objective = obj["objective"]
            wrap = obj.get("wrap", default_wrap)

            if wrap == "jailbreak" and not obj.get("control"):
                # Direct version first, then one case per PyRIT jailbreak template.
                cases.append(TestCase(id=f"{oid}-direct", technique="direct", turns=[objective], **base))
                for t in templates:
                    cases.append(TestCase(id=f"{oid}-pyrit-{t}", technique=f"pyrit:{t}",
                                          turns=[wrap_jailbreak(t, objective)], **base))
            elif wrap == "steal_seed":
                for i, seed in enumerate(_steal_seeds()):
                    cases.append(TestCase(id=f"{oid}-steal-{i}", technique="pyrit:steal_seed",
                                          turns=[seed], **base))
            else:
                cases.append(TestCase(id=f"{oid}", technique="direct", turns=[objective], **base))

    return cases


def suite_summary(cases: list[TestCase]) -> dict:
    by_module: dict[str, int] = {}
    for c in cases:
        by_module[c.module] = by_module.get(c.module, 0) + 1
    return {"total": len(cases), "by_module": by_module, "pyrit_source": pyrit_source()}
