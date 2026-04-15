from __future__ import annotations

from modules.curiosity_engine import CuriosityEngine


def test_generate_contextual_topics_creates_advanced_variants(tmp_path) -> None:
    engine = CuriosityEngine(db_path=str(tmp_path / "knowledge.db"))

    topics = engine._generate_contextual_topics(["telemetry", "vectorstore", "x", "k8s123"])

    assert topics
    assert "telemetry optimization" in topics
    assert "vectorstore for autonomous agents" in topics
    assert all("k8s123" not in topic for topic in topics)


def test_get_next_topic_accepts_context_terms(tmp_path, monkeypatch) -> None:
    engine = CuriosityEngine(db_path=str(tmp_path / "knowledge.db"))
    # força ramo de exploração aleatória
    monkeypatch.setattr("modules.curiosity_engine.random.random", lambda: 0.1)
    monkeypatch.setattr("modules.curiosity_engine.random.choice", lambda seq: seq[-1])

    topic = engine.get_next_topic(context_terms=["telemetry"])

    assert isinstance(topic, str)
    assert topic
    assert "telemetry" in topic or topic in engine.base_topics
