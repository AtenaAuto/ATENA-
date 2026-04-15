from __future__ import annotations

import json

from modules.mission_orchestrator import AtenaMissionOrchestrator, TaskNode


def test_orchestrator_runs_and_persists_checkpoint(tmp_path) -> None:
    orchestrator = AtenaMissionOrchestrator(root_path=tmp_path)

    orchestrator.add_task(
        TaskNode(name="step_a", handler=lambda ctx: {"a": 1})
    )
    orchestrator.add_task(
        TaskNode(name="step_b", handler=lambda ctx: {"b": ctx["a"] + 1})
    )

    result = orchestrator.run(initial_context={"seed": 7})

    assert result["status"] == "ok"
    assert result["context"]["a"] == 1
    assert result["context"]["b"] == 2

    checkpoint_path = tmp_path / "atena_evolution" / "orchestrator_runs" / f"{result['run_id']}.json"
    assert checkpoint_path.exists()

    persisted = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "ok"
    assert len(persisted["steps"]) == 2


def test_orchestrator_uses_fallback_on_failure(tmp_path) -> None:
    orchestrator = AtenaMissionOrchestrator(root_path=tmp_path)

    def failing(_ctx):
        raise RuntimeError("boom")

    def fallback(_ctx):
        return {"recovered": True}

    orchestrator.add_task(
        TaskNode(
            name="step_fallback",
            handler=failing,
            fallback_handler=fallback,
            retries=1,
        )
    )

    result = orchestrator.run()

    assert result["status"] == "ok"
    assert result["context"]["recovered"] is True
    assert result["steps"][0]["status"] == "fallback"
    assert result["steps"][0]["used_fallback"] is True


def test_orchestrator_stops_on_failure_without_continue(tmp_path) -> None:
    orchestrator = AtenaMissionOrchestrator(root_path=tmp_path)

    orchestrator.add_task(TaskNode(name="ok_first", handler=lambda ctx: {"x": 1}))

    def always_fail(_ctx):
        raise ValueError("hard-fail")

    orchestrator.add_task(TaskNode(name="break_here", handler=always_fail))
    orchestrator.add_task(TaskNode(name="never_runs", handler=lambda ctx: {"y": 1}))

    result = orchestrator.run()

    assert result["status"] == "partial"
    assert result["completed_steps"] == 2
    assert result["steps"][1]["status"] == "failed"
    assert result["steps"][1]["error"] == "hard-fail"
