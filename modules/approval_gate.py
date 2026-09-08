"""
AgentGuard Approval Gate
State machine: PENDING -> APPROVED | BLOCKED | AUTO_APPROVED

State transitions:
- READ_ONLY/REVERSIBLE -> AUTO_APPROVED (no human needed)
- DESTRUCTIVE         -> PENDING -> APPROVED (1 approver)
- CATASTROPHIC        -> PENDING -> APPROVED (2 approvers — Senior + Peer)
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import datetime


class GateStatus(Enum):
    AUTO_APPROVED = "AUTO_APPROVED"
    PENDING       = "PENDING"
    APPROVED      = "APPROVED"
    BLOCKED       = "BLOCKED"


@dataclass
class GateDecision:
    action_name:      str
    blast_radius:     int
    risk_score:       float
    status:           GateStatus
    reason:           str
    approvers_needed: int
    approvers_got:    int
    gate_latency_ms:  int = 0
    timestamp:        str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "action_name":      self.action_name,
            "blast_radius":     self.blast_radius,
            "risk_score":       self.risk_score,
            "status":           self.status.value,
            "reason":           self.reason,
            "approvers_needed": self.approvers_needed,
            "approvers_got":    self.approvers_got,
            "gate_latency_ms":  self.gate_latency_ms,
            "timestamp":        self.timestamp,
            "passed":           self.status in (GateStatus.AUTO_APPROVED, GateStatus.APPROVED)
        }


class ApprovalGate:
    """
    Enforces human-in-loop approval for high-risk agentic actions.
    Low-risk actions pass instantly (zero latency overhead).
    High-risk actions are blocked until explicitly approved.

    Design principle: innocent until proven dangerous.
    Default = allow. Exception = block when blast_radius >= DESTRUCTIVE.
    """

    def __init__(self, simulate_approval: bool = True):
        """
        simulate_approval: In demo mode, high-risk actions show PENDING
        status with a simulated approval decision.
        In production, this would call a webhook/notification system.
        """
        self.simulate_approval = simulate_approval
        self._pending_queue: list = []  # Priority queue by blast_radius

    def evaluate(self, classification: dict) -> GateDecision:
        """
        Evaluate a risk classification and return a gate decision.
        """
        blast    = classification["blast_radius"]
        score    = classification["risk_score"]
        needed   = classification["approvers_needed"]
        action   = classification["action"]["name"]

        if blast == 0:
            return GateDecision(
                action_name=action, blast_radius=blast, risk_score=score,
                status=GateStatus.AUTO_APPROVED,
                reason="Read-only action. No state change. Executes immediately.",
                approvers_needed=0, approvers_got=0, gate_latency_ms=0
            )

        if blast == 1:
            return GateDecision(
                action_name=action, blast_radius=blast, risk_score=score,
                status=GateStatus.AUTO_APPROVED,
                reason="Reversible action. State change can be undone. Logged and allowed.",
                approvers_needed=0, approvers_got=0, gate_latency_ms=0
            )

        if blast == 2:
            if self.simulate_approval:
                # Simulate: in dashboard demo, user clicks Approve
                status = GateStatus.PENDING
                reason = (
                    "DESTRUCTIVE action detected. Permanent data loss possible. "
                    "Requires 1 human approver before execution. "
                    "This is the gate that would have prevented the Kiro incident "
                    "if applied to agent actions."
                )
            else:
                status = GateStatus.BLOCKED
                reason = "DESTRUCTIVE action blocked. Awaiting human approval."
            return GateDecision(
                action_name=action, blast_radius=blast, risk_score=score,
                status=status, reason=reason,
                approvers_needed=needed, approvers_got=0
            )

        # blast == 3: CATASTROPHIC
        return GateDecision(
            action_name=action, blast_radius=blast, risk_score=score,
            status=GateStatus.BLOCKED,
            reason=(
                "CATASTROPHIC action blocked. This matches the exact pattern of the "
                "December 2025 AWS Kiro incident (delete + recreate production environment). "
                f"Requires {needed} approvers: Senior Engineer + Peer Review. "
                "No autonomous execution permitted under any circumstances."
            ),
            approvers_needed=needed, approvers_got=0
        )

    def approve(self, decision: GateDecision, approver: str = "demo_user") -> GateDecision:
        """Simulate human approval of a pending decision."""
        if decision.status == GateStatus.PENDING:
            decision.status = GateStatus.APPROVED
            decision.approvers_got = 1
            decision.reason += f" | Approved by: {approver}"
        return decision
