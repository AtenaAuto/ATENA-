from unittest.mock import patch

from core.production_observability import dispatch_alert


class _FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_dispatch_alert_success_mocked():
    with patch("urllib.request.urlopen", return_value=_FakeResponse()):
        payload = dispatch_alert("https://example.com/webhook", {"a": 1})
    assert payload["sent"] is True
    assert payload["http_status"] == 200
