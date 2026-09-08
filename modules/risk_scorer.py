"""
AgentGuard Risk Scorer
Classifies agentic AI actions by blast radius before execution.

OOP Design:
- Action: frozen dataclass (immutable record)
- PrefixTrie: O(1) prefix matching data structure
- RiskScorer: strategy pattern (rule-based classification)

Algorithm complexity:
- Trie insert: O(k) where k = prefix length
- Trie search: O(k) — constant relative to dataset size
- Overall scoring: O(1) per action
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import IntEnum
import re
import json


# ── Blast Radius Levels ───────────────────────────────────────────────────────
class BlastRadius(IntEnum):
    READ_ONLY    = 0   # No state change
    REVERSIBLE   = 1   # State change, can be undone
    DESTRUCTIVE  = 2   # Permanent data loss possible
    CATASTROPHIC = 3   # Production-wide impact

    def label(self) -> str:
        return {
            0: "Read Only",
            1: "Reversible",
            2: "Destructive",
            3: "Catastrophic"
        }[self.value]

    def gate_required(self) -> bool:
        return self.value >= 2

    def approvers_required(self) -> int:
        return {0: 0, 1: 0, 2: 1, 3: 2}[self.value]


# ── Action Data Structure ─────────────────────────────────────────────────────
@dataclass(frozen=True)
class Action:
    """
    Immutable record of an agent action request.
    Frozen dataclass = hashable, thread-safe, prevents mutation after creation.
    """
    name:        str                        # e.g. "delete_table"
    target:      str                        # e.g. "prod-database"
    agent_id:    str                        # e.g. "kiro-agent-01"
    parameters:  dict          = field(default_factory=dict)
    description: str           = ""
    timestamp:   str           = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ── Prefix Trie (O(k) lookup) ─────────────────────────────────────────────────
class PrefixTrie:
    """
    Trie data structure for O(k) action prefix matching.
    k = prefix length (max ~15 chars) — effectively O(1) vs dataset size.

    Why Trie over dict: supports prefix matching without enumerating all keys.
    A dict lookup requires exact match; Trie finds best matching prefix.
    """

    def __init__(self):
        self._root: dict = {}
        self._scores: dict = {}

    def insert(self, prefix: str, score: int) -> None:
        node = self._root
        for char in prefix:
            node = node.setdefault(char, {})
        node["__end__"] = True
        self._scores[prefix] = score

    def search_prefix(self, action_name: str) -> int:
        """
        Find the highest-scoring prefix that matches the start of action_name.
        Returns 0 (READ_ONLY) if no prefix matches.
        """
        best_score = 0
        node = self._root
        matched = []

        for char in action_name:
            if char not in node:
                break
            node = node[char]
            matched.append(char)
            prefix = "".join(matched)
            if "__end__" in node and prefix in self._scores:
                best_score = max(best_score, self._scores[prefix])

        return best_score


# ── Risk Scorer ───────────────────────────────────────────────────────────────
class RiskScorer:
    """
    Classifies agent actions by blast radius using:
    1. Prefix Trie matching on action name
    2. Target environment scoring
    3. Parameter scope analysis

    Final blast_radius = max(prefix_score, target_score, scope_score)
    risk_score (0-100) = (blast_radius / 3) * 100
    """

    # Prefix -> BlastRadius score mapping
    # Source: AWS IAM action taxonomy and common agentic framework conventions
    PREFIX_SCORES = {
        # READ_ONLY (0)
        "get_":         0, "list_":       0, "describe_": 0,
        "fetch_":       0, "search_":     0, "read_":     0,
        "query_":       0, "check_":      0, "view_":     0,

        # REVERSIBLE (1)
        "update_":      1, "modify_":     1, "patch_":    1,
        "put_":         1, "set_":        1, "enable_":   1,
        "disable_":     1, "create_":     1, "add_":      1,
        "insert_":      1, "tag_":        1, "untag_":    1,

        # DESTRUCTIVE (2)
        "delete_":      2, "remove_":     2, "drop_":     2,
        "terminate_":   2, "destroy_":    2, "wipe_":     2,
        "unlink_":      2, "detach_":     2, "revoke_":   2,

        # CATASTROPHIC (3)  ← The Kiro problem lived here
        "recreate_":    3, "reset_prod":  3, "rebuild_":  3,
        "delete_all":   3, "wipe_all":    3, "truncate_": 3,
        "restore_from": 3,  # Restore can overwrite production state
    }

    # Target environment keywords -> score
    TARGET_SCORES = {
        # Production (2)
        "prod":         2, "production":  2, "live":      2,
        "prd":          2, "release":     2,
        # Cross-region bonus (+1 applied separately)
        "all-region":   3, "global":      3, "multi":     3,
        # Staging (1)
        "staging":      1, "uat":         1, "qa":        1,
        "preprod":      1, "pre-prod":    1,
        # Dev/test (0)
        "dev":          0, "test":        0, "local":     0,
        "sandbox":      0, "mock":        0,
    }

    def __init__(self):
        self._trie = PrefixTrie()
        for prefix, score in self.PREFIX_SCORES.items():
            self._trie.insert(prefix, score)

    def score_prefix(self, action_name: str) -> dict:
        """Score based on action name prefix."""
        raw = action_name.lower().strip()
        score = self._trie.search_prefix(raw)
        return {
            "input": action_name,
            "normalized": raw,
            "score": score,
            "method": "Trie prefix match — O(k) lookup",
            "source": "PREFIX_SCORES table in risk_scorer.py"
        }

    def score_target(self, target: str) -> dict:
        """Score based on target environment."""
        t = target.lower()
        score = 0
        matched_keyword = "none"
        for keyword, val in self.TARGET_SCORES.items():
            if keyword in t:
                if val > score:
                    score = val
                    matched_keyword = keyword
        return {
            "input": target,
            "score": score,
            "matched_keyword": matched_keyword,
            "source": "TARGET_SCORES table in risk_scorer.py"
        }

    def score_scope(self, parameters: dict) -> dict:
        """Score based on parameter scope (single vs bulk vs all)."""
        param_str = json.dumps(parameters).lower()
        score = 0
        matched = "no scope keywords"

        scope_patterns = [
            (r"\ball\b",            2, "keyword 'all' — bulk operation"),
            (r"\beverything\b",     2, "keyword 'everything'"),
            (r"\btruncate\b",       2, "keyword 'truncate'"),
            (r"\bforce\b",          1, "keyword 'force' — bypasses confirmation"),
            (r"\bcascade\b",        2, "keyword 'cascade' — affects dependent resources"),
            (r"\brecursive\b",      2, "keyword 'recursive' — tree-wide effect"),
        ]

        for pattern, s, label in scope_patterns:
            if re.search(pattern, param_str):
                if s > score:
                    score = s
                    matched = label

        return {
            "parameters_analyzed": parameters,
            "score": score,
            "matched_pattern": matched,
            "source": "Regex scope pattern matching in risk_scorer.py"
        }

    def classify(self, action: Action) -> dict:
        """
        Full classification of an Action.

        Formula:
            blast_radius = max(prefix_score, target_score, scope_score)
            risk_score = (blast_radius / 3) * 100

        Returns full audit trail of every calculation step.
        """
        prefix_result = self.score_prefix(action.name)
        target_result = self.score_target(action.target)
        scope_result  = self.score_scope(action.parameters)

        blast_value = max(
            prefix_result["score"],
            target_result["score"],
            scope_result["score"]
        )
        blast = BlastRadius(blast_value)
        risk_score = round((blast_value / 3) * 100, 1)

        dominant = max(
            [("prefix",  prefix_result["score"]),
             ("target",  target_result["score"]),
             ("scope",   scope_result["score"])],
            key=lambda x: x[1]
        )[0]

        return {
            "action":          action.to_dict(),
            "blast_radius":    blast_value,
            "blast_label":     blast.label(),
            "risk_score":      risk_score,
            "gate_required":   blast.gate_required(),
            "approvers_needed": blast.approvers_required(),
            "dominant_factor": dominant,
            "formula":         "blast = max(prefix, target, scope); score = (blast/3)*100",
            "calculation": {
                "prefix":  prefix_result,
                "target":  target_result,
                "scope":   scope_result,
                "max_of":  {
                    "prefix": prefix_result["score"],
                    "target": target_result["score"],
                    "scope":  scope_result["score"],
                    "result": blast_value
                }
            },
            "recommendation": (
                "Block. Require 2 approvers (Senior + Peer). "
                "This action matches the Kiro incident pattern."
                if blast_value == 3 else
                "Block. Require human approval before execution."
                if blast_value == 2 else
                "Allow with audit log. No human approval required."
                if blast_value == 1 else
                "Allow immediately. Read-only — no state change."
            )
        }
