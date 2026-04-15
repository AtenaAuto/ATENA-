from pathlib import Path

from core.objective_cycle_runner import run_objective_cycles


class _FakeCore:
    def __init__(self):
        self.generation = 0

    def evolve_one_cycle(self):
        self.generation += 1
        return {
            "generation": self.generation,
            "score": float(self.generation) / 10.0,
            "mutation": "add_comment",
            "replaced": self.generation % 2 == 0,
        }


def test_run_objective_cycles_respects_window(tmp_path: Path):
    seen_topics = []

    def fake_benchmark(topic: str):
        seen_topics.append(topic)
        return {"status": "ok", "confidence": 1.0}

    output = tmp_path / "objective.json"
    payload = run_objective_cycles(
        cycles=10,
        benchmark_window=4,
        topic_template="benchmark cycle {cycle}",
        output_path=output,
        core_factory=_FakeCore,
        benchmark_fn=fake_benchmark,
    )

    assert payload["summary"]["cycles_completed"] == 10
    assert payload["summary"]["benchmarks_executed"] == 3
    assert [b["cycle"] for b in payload["external_benchmarks"]] == [4, 8, 10]
    assert seen_topics == ["benchmark cycle 4", "benchmark cycle 8", "benchmark cycle 10"]
    assert output.exists()


def test_run_objective_cycles_validates_arguments():
    def fake_core_factory():
        return _FakeCore()

    try:
        run_objective_cycles(
            cycles=0,
            benchmark_window=25,
            topic_template="x",
            core_factory=fake_core_factory,
            benchmark_fn=lambda _: {"status": "ok", "confidence": 1.0},
        )
    except ValueError as exc:
        assert "cycles" in str(exc)
    else:
        raise AssertionError("expected ValueError for cycles <= 0")
