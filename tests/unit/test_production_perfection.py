from core.production_perfection import build_perfection_plan


def test_build_perfection_plan_shape():
    payload = build_perfection_plan()
    assert payload["status"] == "in-progress"
    assert isinstance(payload["tracks"], list)
    assert payload["tracks"]
