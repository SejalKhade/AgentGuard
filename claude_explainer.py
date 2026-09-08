"""
AgentGuard — Claude Explanation Layer (optional)

This is NOT a pipeline. The deterministic scorer in pipeline_direct.py is the
pipeline and always runs. This layer is an optional add-on: given the pipeline's
output and an Anthropic API key, it asks Claude to explain the pre-computed scores
in plain English for an engineering manager.

Claude never recalculates a score — it only receives values the Python classifier
produced. HallucinationGuard then checks every number in Claude's reply against
the source data.
"""

import json
import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import anthropic
from modules.hallucination_guard import evaluate as guard_evaluate
from modules.audit_logger import AuditLogger

CLAUDE_MODEL = "claude-sonnet-5"


SYSTEM_PROMPT = """You are a security analyst reviewing agentic AI action risk assessments.

You will receive structured JSON with pre-computed risk scores for a sequence of agent actions.
The scores were computed by a deterministic Python classifier — you did NOT compute them.

Your job:
1. Explain each action's risk in plain English for an engineering manager
2. Identify which actions match the Kiro incident pattern (delete + recreate production)
3. Give 3-5 specific recommendations to reduce blast radius
4. Flag any action sequence that looks like it could cascade (one action enabling another)

Rules:
- Use ONLY the numbers in the JSON. Do not invent or estimate figures.
- Be direct and specific. No filler language.
- If an action is CATASTROPHIC, say so clearly and explain why.

Format:
RISK SUMMARY:
[2-3 sentences on overall risk profile]

ACTION-BY-ACTION ANALYSIS:
[For each action: name, blast label, what it means in plain English]

KIRO PATTERN MATCH:
[Which actions match the December 2025 incident pattern and why]

RECOMMENDATIONS:
[Numbered list of 3-5 specific mitigations]

DATA LIMITATIONS:
[Any caveats about the analysis]"""


def build_prompt(direct_output: dict) -> str:
    """Build a focused prompt from the pipeline output (structured JSON only)."""
    summary_data = {
        "total_actions": direct_output["total"],
        "audit_summary": direct_output["audit_summary"],
        "actions": [
            {
                "name":         r["action"]["name"],
                "target":       r["action"]["target"],
                "agent_id":     r["action"]["agent_id"],
                "blast_radius": r["classification"]["blast_radius"],
                "blast_label":  r["classification"]["blast_label"],
                "risk_score":   r["classification"]["risk_score"],
                "gate_status":  r["gate"]["status"],
                "gate_passed":  r["gate"]["passed"],
                "dominant_factor": r["classification"]["dominant_factor"],
                "recommendation":  r["classification"]["recommendation"]
            }
            for r in direct_output["results"]
        ]
    }
    return (
        "Here are the pre-computed risk assessments. Interpret them.\n\n"
        f"PIPELINE DATA:\n{json.dumps(summary_data, indent=2)}\n\n"
        "Important: Use only the numbers above. Do not estimate or add figures."
    )


def explain(direct_output: dict, api_key: str) -> dict:
    """
    Ask Claude to interpret an already-computed pipeline result.

    Returns {"timestamp", "claude": {...}, "hallucination_guard": {...}}.
    Never raises on an API failure — the error is captured in claude.error and
    claude.success is False.
    """
    if not api_key:
        raise ValueError("Anthropic API key required for the Claude explanation layer")

    prompt = build_prompt(direct_output)
    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        # Join every text block — with adaptive thinking on, content[0] may be a
        # (possibly empty) thinking block rather than the answer.
        claude_text = "".join(
            block.text for block in message.content
            if getattr(block, "type", None) == "text"
        ).strip()
        if not claude_text:
            raise ValueError(f"Claude returned no text (stop_reason={message.stop_reason})")
        claude_success = True
        claude_error = None
    except Exception as e:
        claude_text = ""
        claude_success = False
        claude_error = str(e)

    guard_result = guard_evaluate(claude_text, direct_output)

    AuditLogger().log(
        action_name="claude_explanation",
        pipeline="Claude Explanation Layer",
        classification={
            "action": {"name": "claude_explanation", "target": "all", "agent_id": "claude"},
            "blast_radius": 0, "blast_label": "Read Only", "risk_score": 0.0,
            "gate_required": False, "approvers_needed": 0,
            "dominant_factor": "none", "formula": "N/A",
            "calculation": {}
        },
        gate_decision={"status": "AUTO_APPROVED", "passed": True,
                       "approvers_needed": 0, "approvers_got": 0},
        claude_output={"text": claude_text, "guard": guard_result}
    )

    return {
        "timestamp":          datetime.datetime.now().isoformat(),
        "claude": {
            "success":        claude_success,
            "error":          claude_error,
            "model":          CLAUDE_MODEL,
            "text":           claude_text,
            "prompt_sent":    prompt
        },
        "hallucination_guard": guard_result
    }
