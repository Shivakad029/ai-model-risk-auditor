"""Guardrail building blocks used by the 'governed' (v2) bot.

Each guard has a deterministic implementation so the demo works offline. When
Azure AI Content Safety is configured, Prompt Shields is used as well.
"""

from __future__ import annotations

import base64
import binascii
import re

from .. import llm

PROMPT_CANARY = "CANARY-ABC-7F3A"
CUSTOMER_CANARY = "CANARY-ACCT-1313"
CANARIES = [PROMPT_CANARY, CUSTOMER_CANARY]

ACCOUNT_RE = re.compile(r"\b(?:AB-\d{4}-\d{4}|CANARY-ACCT-\d{4})\b")
CANARY_RE = re.compile(r"CANARY-[A-Z0-9-]+")

INJECTION_PATTERNS = [
    r"ignore (all |any |your |the )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"ignore (your|all) (rules|instructions|guidelines)",
    r"disregard (your|all|the) (rules|instructions|guidelines)",
    r"\b(admin|developer|debug|god|maintenance) mode\b",
    r"(reveal|print|show|repeat|output|tell me) (me )?(your|the) (system prompt|instructions|hidden|internal|configuration)",
    r"system prompt",
    r"you are now (a|an|in)\b",
    r"\bDAN\b|do anything now",
    r"pretend (you are|to be) .* (no|without) (rules|restrictions)",
    r"new instructions?:",
    r"(assistant|ai|model)[, ]+(must|should|will) (now )?(reveal|send|list|transfer|output)",
    r"list (all|every) customers?",
    r"escalation code",
    r"\b(assistant|ai|model) instructions?\s*:",
    r"note (to|for) (the )?(assistant|ai|model)",
    r"\b(ai|assistant|model) (must|should|will) ",
]
_INJECTION_RES = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]
_B64_RE = re.compile(r"\b[A-Za-z0-9+/]{16,}={0,2}")


def decode_base64_chunks(text: str) -> list[str]:
    """Return any printable text hidden in base64 chunks (a common jailbreak trick)."""
    out = []
    for chunk in _B64_RE.findall(text or ""):
        try:
            decoded = base64.b64decode(chunk + "=" * (-len(chunk) % 4), validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if decoded.isprintable() and len(decoded) >= 8:
            out.append(decoded)
    return out


def detect_injection(text: str, is_document: bool = False) -> bool:
    """Heuristic jailbreak / injection detector, backed by Prompt Shields when available."""
    if not text:
        return False
    candidates = [text, *decode_base64_chunks(text)]
    if any(r.search(c) for r in _INJECTION_RES for c in candidates):
        return True
    shield = llm.prompt_shield("" if is_document else text, [text] if is_document else None)
    if shield:
        return shield["document_attack"] if is_document else shield["user_attack"]
    return False


def filter_output(reply: str, allowed_accounts: set[str]) -> tuple[str, bool]:
    """Redact canaries, internal instructions and accounts that don't belong to the user."""
    changed = False
    if "Internal note" in reply or PROMPT_CANARY in reply:
        return ("I'm sorry, I can't share internal configuration or instructions.", True)

    def _redact(m: re.Match) -> str:
        nonlocal changed
        if m.group(0) in allowed_accounts:
            return m.group(0)
        changed = True
        return "[REDACTED]"

    reply = ACCOUNT_RE.sub(_redact, reply)
    if CANARY_RE.search(reply):
        reply = CANARY_RE.sub("[REDACTED]", reply)
        changed = True
    return reply, changed


PROTECTED_RE = [
    re.compile(r"\b\d{5}(?:-\d{4})?\b"),  # zip codes
    re.compile(r"\b(my name is|i am|i'm|name:)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", re.IGNORECASE),
]


def strip_protected_attributes(text: str) -> str:
    """Remove names and zip codes before a credit decision (fair-lending control)."""
    for r in PROTECTED_RE:
        text = r.sub("[REMOVED]", text)
    return text
