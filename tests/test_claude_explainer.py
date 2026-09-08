"""AgentGuard Unit Tests — Claude explanation layer (Anthropic client mocked)"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch
import pytest

import pipeline_direct
import claude_explainer
from modules.audit_logger import AuditLogger


@pytest.fixture(autouse=True)
def fresh_logger():
    AuditLogger.reset()
    yield
    AuditLogger.reset()


def _direct_output():
    return pipeline_direct.run([
        {"name": "get_data", "target": "dev", "agent_id": "a"},
        {"name": "recreate_environment", "target": "prod", "agent_id": "a",
         "parameters": {"all": True}},
    ])


def _text_message(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    msg = MagicMock()
    msg.content = [block]
    msg.stop_reason = "end_turn"
    return msg


def test_missing_key_raises():
    with pytest.raises(ValueError):
        claude_explainer.explain(_direct_output(), "")


def test_build_prompt_is_structured_json_only():
    prompt = claude_explainer.build_prompt(_direct_output())
    assert "PIPELINE DATA:" in prompt
    assert "recreate_environment" in prompt


@patch("claude_explainer.anthropic.Anthropic")
def test_happy_path_runs_guard_and_logs(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _text_message(
        "RISK SUMMARY: 1 catastrophic action of 2 total, risk score 100.0."
    )
    out = claude_explainer.explain(_direct_output(), "sk-ant-test")

    assert out["claude"]["success"] is True
    assert out["claude"]["model"] == claude_explainer.CLAUDE_MODEL
    assert out["hallucination_guard"]["evaluation_performed"] is True
    assert any(
        e["action_name"] == "claude_explanation" for e in AuditLogger().get_all()
    )


@patch("claude_explainer.anthropic.Anthropic")
def test_api_error_is_captured_not_raised(mock_anthropic):
    mock_anthropic.return_value.messages.create.side_effect = RuntimeError("boom")
    out = claude_explainer.explain(_direct_output(), "sk-ant-test")
    assert out["claude"]["success"] is False
    assert "boom" in out["claude"]["error"]
    assert out["hallucination_guard"]["evaluation_performed"] is False


@patch("claude_explainer.anthropic.Anthropic")
def test_empty_response_is_treated_as_failure(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _text_message("   ")
    out = claude_explainer.explain(_direct_output(), "sk-ant-test")
    assert out["claude"]["success"] is False
