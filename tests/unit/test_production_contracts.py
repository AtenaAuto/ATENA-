from core.production_contracts import validate_contract


def test_validate_contract_success():
    payload = {
        "window_days": 7,
        "thresholds": {},
        "summary": {},
        "checks": {},
        "status": "ok",
    }
    assert validate_contract("slo-check", payload) == []


def test_validate_contract_missing_fields():
    errors = validate_contract("tenant-report", {"tenant_id": "t1"})
    assert errors
    assert any("missing field" in e for e in errors)
