"""AgentGuard Unit Tests — guarded agent loop example (Anthropic client mocked)"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch
import pytest

from examples import guarded_agent


def _tool_use(tid, name, inp):
    b = MagicMock()
    b.type = "tool_use"
    b.id = tid
    b.name = name
    b.input = inp
    return b


def _text(t):
    b = MagicMock()
    b.type = "text"
    b.text = t
    return b


def _resp(blocks, stop_reason):
    r = MagicMock()
    r.content = blocks
    r.stop_reason = stop_reason
    return r


@patch("examples.guarded_agent.anthropic.Anthropic")
def test_gate_allows_safe_calls_and_blocks_dangerous_ones(mock_anthropic):
    create = mock_anthropic.return_value.messages.create
    create.side_effect = [
        _resp([
            _tool_use("t1", "scale_deployment",
                      {"env": "staging", "name": "api", "replicas": 5}),
            _tool_use("t2", "delete_deployment", {"env": "staging", "name": "worker"}),
            _tool_use("t3", "recreate_environment",
                      {"env": "prod-cost-explorer", "force": True}),
        ], "tool_use"),
        _resp([_text("Scaled api. Delete and prod rebuild were blocked for approval.")],
              "end_turn"),
    ]

    events = guarded_agent.run("tidy up", api_key="sk-ant-test")
    by_tool = {e.get("tool"): e for e in events if "tool" in e}

    assert by_tool["scale_deployment"]["type"] == "allowed"
    assert by_tool["delete_deployment"]["type"] == "blocked"       # DESTRUCTIVE
    assert by_tool["recreate_environment"]["type"] == "blocked"    # CATASTROPHIC
    assert events[-1]["type"] == "final"


@patch("examples.guarded_agent.anthropic.Anthropic")
def test_blocked_call_returns_is_error_tool_result_to_claude(mock_anthropic):
    create = mock_anthropic.return_value.messages.create
    create.side_effect = [
        _resp([_tool_use("t1", "recreate_environment", {"env": "prod", "force": True})],
              "tool_use"),
        _resp([_text("Understood — I won't recreate prod.")], "end_turn"),
    ]

    guarded_agent.run("rebuild prod", api_key="sk-ant-test")

    # A tool_result carrying is_error must have been fed back to Claude.
    sent_messages = create.call_args_list[-1].kwargs["messages"]
    tool_results = [
        block
        for msg in sent_messages
        if isinstance(msg["content"], list)
        for block in msg["content"]
        if isinstance(block, dict) and block.get("type") == "tool_result"
    ]
    t1 = next(r for r in tool_results if r["tool_use_id"] == "t1")
    assert t1["is_error"] is True
    assert "BLOCKED by AgentGuard" in t1["content"]


@patch("examples.guarded_agent.anthropic.Anthropic")
def test_stops_when_claude_stops_asking_for_tools(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = _resp(
        [_text("Nothing to do.")], "end_turn"
    )
    events = guarded_agent.run("noop", api_key="sk-ant-test")
    assert events == [{"type": "final", "text": "Nothing to do."}]
