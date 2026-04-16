import json
from unittest.mock import patch
from urllib.error import HTTPError

from core.internet_challenge import run_internet_challenge


class _FakeResponse:
    def __init__(self, payload):  # noqa: ANN001
        self._payload = payload

    def read(self) -> bytes:
        if isinstance(self._payload, str):
            return self._payload.encode("utf-8")
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _fake_urlopen(url, timeout: int = 15):  # noqa: ANN001
    target = url.full_url if hasattr(url, "full_url") else str(url)
    if "export.arxiv.org" in target:
        xml = """<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom'>
  <entry><title>Paper One</title></entry>
</feed>"""
        return _FakeResponse(xml)
    if "wikipedia" in target:
        return _FakeResponse({"title": "AI", "extract": "Artificial intelligence summary"})
    if "github" in target:
        return _FakeResponse({"items": [{"full_name": "org/repo", "stargazers_count": 10}]})
    return _FakeResponse({"hits": [{"title": "HN story", "points": 42}]})


def test_run_internet_challenge_mocked():
    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        payload = run_internet_challenge("artificial intelligence")
    assert payload["status"] == "ok"
    assert payload["confidence"] == 1.0
    assert len(payload["sources"]) == 4


def test_run_internet_challenge_wikipedia_fallback_search():
    def _urlopen_with_wiki_fallback(url, timeout: int = 15):  # noqa: ANN001
        target = url.full_url if hasattr(url, "full_url") else str(url)
        if "export.arxiv.org" in target:
            xml = """<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom'>
  <entry><title>Paper One</title></entry>
</feed>"""
            return _FakeResponse(xml)
        if "api/rest_v1/page/summary" in target and "artificial%20intelligence" in target:
            raise HTTPError(target, 404, "Not Found", hdrs=None, fp=None)
        if "w/api.php?action=opensearch" in target:
            return _FakeResponse(["artificial intelligence", ["Artificial intelligence"], [], []])
        if "api/rest_v1/page/summary/Artificial%20intelligence" in target:
            return _FakeResponse({"title": "Artificial intelligence", "extract": "Fallback extract"})
        if "github" in target:
            return _FakeResponse({"items": [{"full_name": "org/repo", "stargazers_count": 10}]})
        return _FakeResponse({"hits": [{"title": "HN story", "points": 42}]})

    with patch("urllib.request.urlopen", side_effect=_urlopen_with_wiki_fallback):
        payload = run_internet_challenge("artificial intelligence")
    wiki = payload["sources"][0]
    assert wiki["ok"] is True
    assert wiki["details"].get("fallback_search") is True
