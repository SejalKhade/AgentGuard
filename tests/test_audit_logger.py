"""AgentGuard Unit Tests — AuditLogger"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import pytest

from modules.audit_logger import AuditLogger
from modules.approval_gate import ApprovalGate
from modules.risk_scorer import RiskScorer, Action


@pytest.fixture(autouse=True)
def fresh_logger():
    AuditLogger.reset()
    yield
    AuditLogger.reset()


@pytest.fixture
def scorer():
    return RiskScorer()


@pytest.fixture
def gate():
    return ApprovalGate(simulate_approval=True)


def _entry(scorer, gate, name, target, params=None, claude_output=None):
    action = Action(name=name, target=target, agent_id="agent-7",
                    parameters=params or {})
    classification = scorer.classify(action)
    decision = gate.evaluate(classification).to_dict()
    logger = AuditLogger()
    return logger.log(name, "direct", classification, decision, claude_output)


class TestAuditLogger:
    def test_singleton_identity(self):
        assert AuditLogger() is AuditLogger()

    def test_reset_creates_new_instance(self):
        first = AuditLogger()
        AuditLogger.reset()
        assert AuditLogger() is not first

    def test_log_entry_shape(self, scorer, gate):
        entry = _entry(scorer, gate, "get_data", "dev-env")
        assert entry["pk"] == "agent-7"
        assert entry["action_name"] == "get_data"
        assert entry["pipeline"] == "direct"
        assert entry["sk"].endswith("#get_data")
        assert entry["ttl"] > 0
        assert AuditLogger().get_all() == [entry]

    def test_get_all_returns_copy(self, scorer, gate):
        _entry(scorer, gate, "get_data", "dev-env")
        snapshot = AuditLogger().get_all()
        snapshot.append("mutation")
        assert len(AuditLogger().get_all()) == 1

    def test_summary_empty(self):
        assert AuditLogger().get_summary() == {"total": 0}

    def test_summary_aggregates(self, scorer, gate):
        _entry(scorer, gate, "get_data", "dev-env")
        _entry(scorer, gate, "delete_table", "prod-db")
        _entry(scorer, gate, "recreate_environment", "prod",
               {"force": True, "all": True})
        summary = AuditLogger().get_summary()
        assert summary["total_actions"] == 3
        assert summary["catastrophic_count"] == 1
        assert summary["destructive_count"] == 1
        assert summary["auto_passed"] == 1
        assert summary["blocked_or_pending"] == 2
        assert summary["block_rate_pct"] == 66.7
        assert summary["pipelines_used"] == ["direct"]

    def test_export_json_roundtrips(self, scorer, gate):
        _entry(scorer, gate, "get_data", "dev-env",
               claude_output={"summary": "safe"})
        parsed = json.loads(AuditLogger().export_json())
        assert isinstance(parsed, list)
        assert parsed[0]["claude_output"] == {"summary": "safe"}
