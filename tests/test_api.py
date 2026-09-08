"""AgentGuard Unit Tests — FastAPI service"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

import api

client = TestClient(api.app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "agentguard"


def test_score_read_only_is_allowed():
    r = client.post("/score", json={
        "name": "get_data", "target": "dev-env", "agent_id": "a",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is True
    assert body["classification"]["blast_radius"] == 0
    assert body["gate"]["status"] == "AUTO_APPROVED"


def test_score_kiro_action_is_blocked():
    r = client.post("/score", json={
        "name": "recreate_environment",
        "target": "prod-cost-explorer-china",
        "agent_id": "kiro-agent-01",
        "parameters": {"force": True, "all": True},
    })
    body = r.json()
    assert body["allowed"] is False
    assert body["classification"]["blast_radius"] == 3
    assert body["gate"]["status"] == "BLOCKED"
    assert body["gate"]["approvers_needed"] == 2


def test_score_requires_name_and_target():
    r = client.post("/score", json={"agent_id": "a"})
    assert r.status_code == 422


def test_score_batch_runs_full_pipeline():
    r = client.post("/score/batch", json=[
        {"name": "get_data", "target": "dev", "agent_id": "a"},
        {"name": "delete_table", "target": "prod-db", "agent_id": "a"},
        {"name": "recreate_environment", "target": "prod", "agent_id": "a",
         "parameters": {"all": True}},
    ])
    body = r.json()
    assert body["total"] == 3
    assert body["audit_summary"]["blocked_or_pending"] == 2
    assert body["audit_summary"]["catastrophic_count"] == 1
