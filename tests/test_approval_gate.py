"""AgentGuard Unit Tests — ApprovalGate"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from modules.approval_gate import ApprovalGate, GateStatus
from modules.risk_scorer import RiskScorer, Action


@pytest.fixture
def gate():
    return ApprovalGate(simulate_approval=True)


@pytest.fixture
def scorer():
    return RiskScorer()


def classify(scorer, name, target, params=None):
    a = Action(name=name, target=target, agent_id="test",
               parameters=params or {})
    return scorer.classify(a)


class TestApprovalGate:
    def test_read_only_auto_approved(self, gate, scorer):
        c = classify(scorer, "get_data", "dev-env")  # dev target keeps blast at 0
        d = gate.evaluate(c)
        assert d.status == GateStatus.AUTO_APPROVED
        assert d.to_dict()["passed"] is True

    def test_reversible_auto_approved(self, gate, scorer):
        c = classify(scorer, "update_config", "dev")
        d = gate.evaluate(c)
        assert d.status == GateStatus.AUTO_APPROVED

    def test_destructive_is_pending(self, gate, scorer):
        c = classify(scorer, "delete_table", "prod-db")
        d = gate.evaluate(c)
        assert d.status == GateStatus.PENDING
        assert d.approvers_needed == 1

    def test_catastrophic_is_blocked(self, gate, scorer):
        c = classify(scorer, "recreate_environment", "prod",
                     {"force": True, "all": True})
        d = gate.evaluate(c)
        assert d.status == GateStatus.BLOCKED
        assert d.approvers_needed == 2
        assert d.to_dict()["passed"] is False

    def test_approve_pending(self, gate, scorer):
        c = classify(scorer, "delete_table", "prod-db")
        d = gate.evaluate(c)
        assert d.status == GateStatus.PENDING
        approved = gate.approve(d, "senior-engineer")
        assert approved.status == GateStatus.APPROVED
        assert approved.approvers_got == 1
