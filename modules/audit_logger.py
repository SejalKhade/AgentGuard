"""
AgentGuard Audit Logger
DynamoDB-compatible JSON audit trail.
Singleton pattern — one logger per session.
Every action, every gate decision, every Claude output is logged.
"""

from __future__ import annotations
from typing import ClassVar
import datetime
import json


class AuditLogger:
    """
    Singleton audit logger.
    Stores entries in memory (ordered dict) + exportable as JSON.
    Schema matches AWS DynamoDB item format for production compatibility.
    """
    _instance: ClassVar[Optional[AuditLogger]] = None
    _log: list

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._log = []
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset for new session (used in tests and dashboard)."""
        cls._instance = None

    def log(self,
            action_name:  str,
            pipeline:     str,
            classification: dict,
            gate_decision: dict,
            claude_output: dict = None) -> dict:
        """
        Write a structured audit entry.
        DynamoDB-compatible: pk = agent_id, sk = timestamp#action_name
        """
        entry = {
            "pk":              classification["action"].get("agent_id", "unknown"),
            "sk":              f"{datetime.datetime.now().isoformat()}#{action_name}",
            "pipeline":        pipeline,
            "action_name":     action_name,
            "action_target":   classification["action"].get("target", ""),
            "blast_radius":    classification["blast_radius"],
            "blast_label":     classification["blast_label"],
            "risk_score":      classification["risk_score"],
            "gate_status":     gate_decision.get("status", "UNKNOWN"),
            "gate_passed":     gate_decision.get("passed", False),
            "approvers_needed": gate_decision.get("approvers_needed", 0),
            "formula_used":    classification["formula"],
            "calculation_trace": classification["calculation"],
            "claude_output":   claude_output,
            "logged_at":       datetime.datetime.now().isoformat(),
            "ttl":             int(datetime.datetime.now().timestamp()) + 86400 * 30
        }
        self._log.append(entry)
        return entry

    def get_all(self) -> list:
        return self._log.copy()

    def get_summary(self) -> dict:
        if not self._log:
            return {"total": 0}
        total = len(self._log)
        blocked = sum(1 for e in self._log if not e["gate_passed"])
        catastrophic = sum(1 for e in self._log if e["blast_radius"] == 3)
        destructive  = sum(1 for e in self._log if e["blast_radius"] == 2)
        auto_passed  = sum(1 for e in self._log if e["blast_radius"] <= 1)
        return {
            "total_actions":       total,
            "auto_passed":         auto_passed,
            "blocked_or_pending":  blocked,
            "catastrophic_count":  catastrophic,
            "destructive_count":   destructive,
            "block_rate_pct":      round(blocked / total * 100, 1) if total else 0,
            "pipelines_used":      list({e["pipeline"] for e in self._log})
        }

    def export_json(self) -> str:
        return json.dumps(self._log, indent=2, default=str)
