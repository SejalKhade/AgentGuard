"""
AgentGuard Unit Tests — RiskScorer
Target: 90%+ coverage

Tests cover:
- Trie prefix matching (data structure correctness)
- All four blast radius levels
- Target environment scoring
- Scope parameter detection
- Edge cases (empty input, unknown prefixes)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from modules.risk_scorer import RiskScorer, Action, BlastRadius, PrefixTrie


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture
def scorer():
    return RiskScorer()


def make_action(name, target="dev-env", params=None, agent="test-agent"):
    return Action(name=name, target=target,
                  parameters=params or {}, agent_id=agent)


# ── Trie Tests ────────────────────────────────────────────────────────────────
class TestPrefixTrie:
    def test_insert_and_search_exact(self):
        trie = PrefixTrie()
        trie.insert("delete_", 2)
        assert trie.search_prefix("delete_table") == 2

    def test_search_no_match(self):
        trie = PrefixTrie()
        trie.insert("delete_", 2)
        assert trie.search_prefix("fetch_data") == 0

    def test_search_higher_score_wins(self):
        trie = PrefixTrie()
        trie.insert("delete_", 2)
        trie.insert("delete_all", 3)
        assert trie.search_prefix("delete_all_records") == 3

    def test_empty_action_name(self):
        trie = PrefixTrie()
        trie.insert("delete_", 2)
        assert trie.search_prefix("") == 0


# ── BlastRadius Tests ─────────────────────────────────────────────────────────
class TestBlastRadius:
    def test_read_only_no_gate(self):
        assert BlastRadius.READ_ONLY.gate_required() is False

    def test_reversible_no_gate(self):
        assert BlastRadius.REVERSIBLE.gate_required() is False

    def test_destructive_needs_gate(self):
        assert BlastRadius.DESTRUCTIVE.gate_required() is True

    def test_catastrophic_needs_gate(self):
        assert BlastRadius.CATASTROPHIC.gate_required() is True

    def test_approvers_catastrophic(self):
        assert BlastRadius.CATASTROPHIC.approvers_required() == 2

    def test_approvers_read_only(self):
        assert BlastRadius.READ_ONLY.approvers_required() == 0


# ── Prefix Scoring Tests ──────────────────────────────────────────────────────
class TestPrefixScoring:
    def test_get_is_read_only(self, scorer):
        r = scorer.score_prefix("get_cost_data")
        assert r["score"] == 0

    def test_list_is_read_only(self, scorer):
        r = scorer.score_prefix("list_s3_buckets")
        assert r["score"] == 0

    def test_update_is_reversible(self, scorer):
        r = scorer.score_prefix("update_config")
        assert r["score"] == 1

    def test_delete_is_destructive(self, scorer):
        r = scorer.score_prefix("delete_table")
        assert r["score"] == 2

    def test_recreate_is_catastrophic(self, scorer):
        r = scorer.score_prefix("recreate_environment")
        assert r["score"] == 3

    def test_unknown_prefix_defaults_to_zero(self, scorer):
        r = scorer.score_prefix("unknown_operation")
        assert r["score"] == 0


# ── Target Scoring Tests ──────────────────────────────────────────────────────
class TestTargetScoring:
    def test_dev_is_zero(self, scorer):
        assert scorer.score_target("dev-database")["score"] == 0

    def test_staging_is_one(self, scorer):
        assert scorer.score_target("staging-api")["score"] == 1

    def test_prod_is_two(self, scorer):
        assert scorer.score_target("prod-cost-explorer")["score"] == 2

    def test_global_is_three(self, scorer):
        assert scorer.score_target("global-production")["score"] == 3

    def test_empty_target(self, scorer):
        assert scorer.score_target("")["score"] == 0


# ── Full Classification Tests ─────────────────────────────────────────────────
class TestClassify:
    def test_kiro_incident_action_is_catastrophic(self, scorer):
        """The exact action that caused the Dec 2025 outage."""
        action = make_action(
            name="recreate_environment",
            target="prod-cost-explorer-china",
            params={"force": True, "all": True}
        )
        result = scorer.classify(action)
        assert result["blast_radius"] == 3
        assert result["risk_score"] == 100.0
        assert result["gate_required"] is True
        assert result["approvers_needed"] == 2

    def test_read_action_is_safe(self, scorer):
        action = make_action("get_cost_data", "dev-env")
        result = scorer.classify(action)
        assert result["blast_radius"] == 0
        assert result["gate_required"] is False

    def test_delete_prod_is_destructive(self, scorer):
        action = make_action("delete_table", "prod-database")
        result = scorer.classify(action)
        assert result["blast_radius"] == 2
        assert result["gate_required"] is True

    def test_result_has_full_audit_trail(self, scorer):
        action = make_action("delete_table", "staging-db")
        result = scorer.classify(action)
        assert "calculation" in result
        assert "prefix" in result["calculation"]
        assert "target" in result["calculation"]
        assert "scope" in result["calculation"]
        assert "formula" in result

    def test_risk_score_range(self, scorer):
        for name in ["get_data", "update_cfg", "delete_tbl", "recreate_env"]:
            action = make_action(name, "prod")
            r = scorer.classify(action)
            assert 0 <= r["risk_score"] <= 100

    def test_scope_cascade_increases_score(self, scorer):
        """Parameters with 'all' keyword should escalate risk."""
        action = make_action(
            "update_config",
            "dev-env",
            params={"scope": "all", "cascade": True}
        )
        result = scorer.classify(action)
        # Scope has 'all' and 'cascade' — should push above REVERSIBLE
        assert result["blast_radius"] >= 2
