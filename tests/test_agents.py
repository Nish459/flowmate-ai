"""Structural tests for the ADK agent skeleton -- confirms every agent
module exposes `root_agent` (the ADK CLI discovery convention) and that the
orchestrator wires the fan-out/fan-in shape from the project architecture,
without making any real Gemini or BigQuery calls.
"""


def test_each_agent_module_exposes_a_root_agent_with_a_tool():
    from agents.bottleneck_detector.agent import root_agent as bottleneck_detector
    from agents.review_nudger.agent import root_agent as review_nudger
    from agents.standup_writer.agent import root_agent as standup_writer
    from agents.ticket_watcher.agent import root_agent as ticket_watcher

    for agent in (ticket_watcher, review_nudger, standup_writer, bottleneck_detector):
        assert agent.tools, f"{agent.name} has no tools wired"

    assert len(bottleneck_detector.tools) == 3  # needs all 3 tables per the doc


def test_orchestrator_wires_fan_out_then_fan_in():
    from agents.orchestrator.agent import root_agent

    assert root_agent.name == "flowmate_orchestrator"
    assert [a.name for a in root_agent.sub_agents] == ["watch_and_detect", "nudge_and_summarize"]

    watch_and_detect, nudge_and_summarize = root_agent.sub_agents
    assert [a.name for a in watch_and_detect.sub_agents] == ["ticket_watcher", "bottleneck_detector"]
    assert [a.name for a in nudge_and_summarize.sub_agents] == ["review_nudger", "standup_writer"]
