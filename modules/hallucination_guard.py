"""
AgentGuard Hallucination Guard
Verifies every numerical claim in Claude's output against source pipeline data.

Three-step process:
1. Extract all numbers from Claude's text via regex
2. Compare each against source JSON within tolerance
3. Return per-claim VERIFIED / APPROXIMATION / UNVERIFIED table
"""

from __future__ import annotations
import re


def extract_numbers(text: str) -> list[dict]:
    """Extract all numbers and surrounding context from text."""
    pattern = r"(?<![a-zA-Z])(-?\d+\.?\d*)\s*(%|ms|hrs?|hours?|minutes?|actions?|approvers?)?"
    matches = []
    for m in re.finditer(pattern, text):
        start = max(0, m.start() - 70)
        end   = min(len(text), m.end() + 70)
        matches.append({
            "number":  float(m.group(1)),
            "unit":    m.group(2) or "",
            "context": text[start:end].strip()
        })
    return matches


def get_source_numbers(pipeline_output: dict) -> list[dict]:
    """Recursively extract all numbers from pipeline output (source of truth)."""
    numbers = []

    def recurse(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                recurse(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                recurse(item, f"{path}[{i}]")
        elif isinstance(obj, (int, float)):
            numbers.append({"value": float(obj), "path": path})

    recurse(pipeline_output)
    return numbers


def verify_claim(claimed: float, sources: list[dict], tolerance: float = 0.05) -> dict:
    """Check if a claimed number exists in source data within tolerance."""
    for src in sources:
        sv = src["value"]
        if sv == 0:
            continue
        diff = abs(claimed - sv) / abs(sv)
        if diff <= tolerance:
            return {
                "status":         "VERIFIED",
                "matched_value":  sv,
                "source_path":    src["path"],
                "difference_pct": round(diff * 100, 2)
            }
        if diff <= 0.15:
            return {
                "status":         "APPROXIMATION",
                "matched_value":  sv,
                "source_path":    src["path"],
                "difference_pct": round(diff * 100, 2),
                "note":           "Within 15% — likely rounding"
            }
    return {
        "status":      "UNVERIFIED",
        "matched_value": None,
        "source_path": None,
        "note":        "Not traceable to pipeline source data"
    }


def evaluate(claude_text: str, pipeline_output: dict) -> dict:
    """Full hallucination evaluation of Claude's output."""
    if not claude_text or not pipeline_output:
        return {"evaluation_performed": False, "reason": "Missing input"}

    sources  = get_source_numbers(pipeline_output)
    claimed  = [c for c in extract_numbers(claude_text) if abs(c["number"]) >= 1.0]

    results  = []
    verified = approx = unverified = 0

    for claim in claimed:
        v = verify_claim(claim["number"], sources)
        results.append({
            "claimed_number": claim["number"],
            "unit":           claim["unit"],
            "context":        claim["context"][:100],
            "verification":   v
        })
        if v["status"] == "VERIFIED":
            verified += 1
        elif v["status"] == "APPROXIMATION":
            approx += 1
        else:
            unverified += 1

    total = len(results)
    reliability = round((verified + approx * 0.5) / total * 100, 1) if total else 100.0
    status = (
        "RELIABLE"          if reliability >= 80 else
        "PARTIALLY RELIABLE" if reliability >= 60 else
        "REVIEW REQUIRED"
    )

    return {
        "evaluation_performed": True,
        "total_claims":         total,
        "verified":             verified,
        "approximations":       approx,
        "unverified":           unverified,
        "reliability_score":    reliability,
        "overall_status":       status,
        "claim_results":        results,
        "methodology": (
            "Numbers extracted via regex. Each compared against all numeric values "
            "in pipeline source JSON. VERIFIED = within 5%. "
            "APPROXIMATION = within 15%. UNVERIFIED = not found."
        ),
        "note": (
            "Claude receives pre-computed scores as structured JSON. "
            "Score hallucinations are structurally prevented — "
            "Claude interprets numbers it did not calculate."
        )
    }
