"""
AgentGuard Pipeline 1: Direct Pipeline
Fully deterministic. No LLM. No API calls.
Same input always produces same output.

OOP: Uses Action, RiskScorer, ApprovalGate, AuditLogger classes.
Algorithm: O(1) risk scoring via Trie + hash lookups.
"""

import json
import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from modules.risk_scorer import RiskScorer, Action
from modules.approval_gate import ApprovalGate
from modules.audit_logger import AuditLogger

# Shared stateless scorer (the prefix Trie is built once in __init__).
_SCORER = RiskScorer()


def score_one(action: dict) -> dict:
    """
    Score a single action dict (no audit logging, no shared state).

    Returns {action, classification, gate, allowed} — the same shape the REST
    API returns and the contract an agent runtime checks before executing a tool.
    """
    act = Action(
        name=action.get("name", ""),
        target=action.get("target", ""),
        agent_id=action.get("agent_id", "unknown"),
        parameters=action.get("parameters", {}),
        description=action.get("description", ""),
        timestamp=datetime.datetime.now().isoformat(),
    )
    classification = _SCORER.classify(act)
    decision = ApprovalGate(simulate_approval=True).evaluate(classification).to_dict()
    return {
        "action":         act.to_dict(),
        "classification": classification,
        "gate":           decision,
        "allowed":        decision["passed"],
    }


def run(actions_input: list[dict]) -> dict:
    """
    Run direct pipeline on a list of action dicts.
    Returns full results with audit trail per action.
    """
    scorer  = RiskScorer()
    gate    = ApprovalGate(simulate_approval=True)
    logger  = AuditLogger()

    results = []
    for raw in actions_input:
        action = Action(
            name=raw.get("name", ""),
            target=raw.get("target", ""),
            agent_id=raw.get("agent_id", "unknown"),
            parameters=raw.get("parameters", {}),
            description=raw.get("description", ""),
            timestamp=datetime.datetime.now().isoformat()
        )

        classification = scorer.classify(action)
        gate_decision  = gate.evaluate(classification)
        log_entry      = logger.log(
            action_name=action.name,
            pipeline="Direct Pipeline",
            classification=classification,
            gate_decision=gate_decision.to_dict()
        )

        results.append({
            "action":         action.to_dict(),
            "classification": classification,
            "gate":           gate_decision.to_dict(),
            "logged":         True
        })

    return {
        "pipeline":    "Direct Pipeline (No LLM)",
        "timestamp":   datetime.datetime.now().isoformat(),
        "total":       len(results),
        "results":     results,
        "audit_summary": logger.get_summary()
    }


if __name__ == "__main__":
    with open("data/sample_actions.json") as f:
        actions = json.load(f)
    output = run(actions)
    print(json.dumps(output, indent=2, default=str))
