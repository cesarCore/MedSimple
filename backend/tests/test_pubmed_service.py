import unittest
from unittest.mock import MagicMock

from backend import pubmed_service


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FetchCitationsTests(unittest.TestCase):
    def test_empty_query_returns_empty(self):
        self.assertEqual(pubmed_service.fetch_citations("   "), [])

    def test_happy_path_returns_citations(self):
        calls = []

        def fake_get(url, params, timeout):
            calls.append((url, params))
            if "esearch" in url:
                return FakeResponse({"esearchresult": {"idlist": ["111", "222"]}})
            return FakeResponse({
                "result": {
                    "111": {"title": "Aspirin study"},
                    "222": {"title": "Ibuprofen study"},
                }
            })

        citations = pubmed_service.fetch_citations(
            "aspirin side effects", http_get=fake_get
        )
        self.assertEqual(len(citations), 2)
        self.assertEqual(citations[0]["pmid"], "111")
        self.assertEqual(citations[0]["title"], "Aspirin study")
        self.assertTrue(citations[0]["url"].endswith("/111/"))
        self.assertEqual(calls[0][1]["term"], "aspirin side effects")

    def test_no_pmids_returns_empty(self):
        def fake_get(url, params, timeout):
            return FakeResponse({"esearchresult": {"idlist": []}})

        self.assertEqual(
            pubmed_service.fetch_citations("x", http_get=fake_get), []
        )

    def test_http_error_is_swallowed(self):
        def fake_get(url, params, timeout):
            return FakeResponse({}, status=500)

        self.assertEqual(
            pubmed_service.fetch_citations("x", http_get=fake_get), []
        )

    def test_api_key_is_forwarded(self):
        seen = {}

        def fake_get(url, params, timeout):
            seen.setdefault("params", params)
            if "esearch" in url:
                return FakeResponse({"esearchresult": {"idlist": ["1"]}})
            return FakeResponse({"result": {"1": {"title": "t"}}})

        pubmed_service.fetch_citations("x", api_key="KEY", http_get=fake_get)
        self.assertEqual(seen["params"]["api_key"], "KEY")


if __name__ == "__main__":
    unittest.main()
