"""Regulatory mapping: ties each module and finding to the controls a bank's model
risk and audit teams already use (SR 11-7, NIST AI RMF, OWASP LLM Top 10, ECOA/Reg B).

This maps evidence to frameworks; it does NOT assert compliance. A passing audit is
one input to a control, not a sign-off.
"""

from __future__ import annotations

MODULE_FRAMEWORKS = {
    "prompt_injection": {
        "owasp": "LLM01: Prompt Injection",
        "nist": "MEASURE 2.7 (security & resilience), MANAGE 2.2",
        "sr_11_7": "Ongoing monitoring — challenge the model against adversarial inputs",
    },
    "doc_injection": {
        "owasp": "LLM01: Prompt Injection (indirect)",
        "nist": "MEASURE 2.7, MAP 4.1 (third-party / data provenance)",
        "sr_11_7": "Input data controls and model use limits",
    },
    "data_leakage": {
        "owasp": "LLM02: Sensitive Information Disclosure",
        "nist": "MEASURE 2.10 (privacy), GOVERN 1.2",
        "sr_11_7": "Data confidentiality; conceptual soundness of access controls",
    },
    "hallucination": {
        "owasp": "LLM09: Misinformation",
        "nist": "MEASURE 2.9 (model output validity), 2.3",
        "sr_11_7": "Outcomes analysis — accuracy and grounding of outputs",
    },
    "fair_lending": {
        "owasp": "Fair lending — outside OWASP scope",
        "nist": "MEASURE 2.11 (fairness & bias), GOVERN 3.2",
        "sr_11_7": "Outcomes analysis for disparate impact",
        "ecoa": "ECOA / Reg B — no decision use of a prohibited basis or proxy",
    },
    "excessive_agency": {
        "owasp": "LLM06: Excessive Agency",
        "nist": "MANAGE 2.2, MEASURE 2.7",
        "sr_11_7": "Model use controls; authorization before consequential actions",
    },
}

FRAMEWORK_LABELS = {
    "owasp": "OWASP Top 10 for LLM Applications",
    "nist": "NIST AI RMF 1.0",
    "sr_11_7": "SR 11-7 (model risk management)",
    "ecoa": "ECOA / Regulation B (fair lending)",
}


def mapping_rows() -> list[dict]:
    """Flat rows for the report's regulatory-mapping table."""
    rows = []
    for module, fw in MODULE_FRAMEWORKS.items():
        for key, ref in fw.items():
            rows.append({"module": module, "framework": FRAMEWORK_LABELS[key], "control": ref})
    return rows


def frameworks_for(module: str) -> dict:
    return MODULE_FRAMEWORKS.get(module, {})
