import json
import unittest
from unittest.mock import MagicMock

from backend import analysis_service


def make_openai_client(responses):
    """Return a stub openai client that yields `responses` in order from chat.completions.create."""
    iterator = iter(responses)

    def create(**_kwargs):
        payload = next(iterator)
        message = MagicMock()
        message.content = json.dumps(payload)
        choice = MagicMock()
        choice.message = message
        response = MagicMock()
        response.choices = [choice]
        return response

    client = MagicMock()
    client.chat.completions.create.side_effect = create
    return client


class AnalyzeTests(unittest.TestCase):
    def test_happy_path_attaches_only_pubmed_citations(self):
        extraction = {
            "product": {
                "raw_name": "Aspirin 500mg",
                "normalized_name": "aspirin",
                "product_type": "otc",
                "dosage_text": "500mg",
            },
            "ingredients": [
                {"name_raw": "Aspirin", "name_normalized": "aspirin", "confidence": 0.9}
            ],
            "specialist_types": ["pharmacy"],
            "symptoms_or_risks": ["bleeding"],
        }
        findings = {
            "summary": "Aspirin is widely studied.",
            "effects": ["GI bleeding"],
            "severity": "moderate",
        }
        client = make_openai_client([extraction, findings])

        citations = [
            {"pmid": "1", "title": "Aspirin and bleeding", "url": "u1"},
            {"pmid": "2", "title": "NSAID safety", "url": "u2"},
        ]
        fetcher = MagicMock(return_value=citations)

        result = analysis_service.analyze(
            {"full_text": "Aspirin 500mg", "average_confidence": 0.9},
            openai_client=client,
            citation_fetcher=fetcher,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["product"]["normalized_name"], "aspirin")
        self.assertEqual(len(result["clinical_findings"]), 1)
        finding = result["clinical_findings"][0]
        self.assertEqual(finding["ingredient"], "aspirin")
        self.assertEqual(finding["citations"], citations)
        self.assertEqual(finding["severity"], "moderate")
        fetcher.assert_called_once_with("aspirin side effects")

    def test_no_citations_sets_unknown_severity_and_skips_second_llm_call(self):
        extraction = {
            "ingredients": [
                {"name_raw": "Foo", "name_normalized": "foo", "confidence": 0.5}
            ],
            "specialist_types": [],
            "symptoms_or_risks": [],
            "product": {},
        }
        client = make_openai_client([extraction])  # only extraction call expected
        result = analysis_service.analyze(
            {"full_text": "Foo"},
            openai_client=client,
            citation_fetcher=lambda q: [],
        )
        finding = result["clinical_findings"][0]
        self.assertEqual(finding["severity"], "unknown")
        self.assertEqual(finding["citations"], [])
        self.assertEqual(client.chat.completions.create.call_count, 1)

    def test_extraction_failure_yields_empty_ingredients_and_warning(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("boom")

        result = analysis_service.analyze(
            {"full_text": "x"},
            openai_client=client,
            citation_fetcher=lambda q: [],
        )
        self.assertEqual(result["ingredients"], [])
        self.assertTrue(any("extraction failed" in w for w in result["warnings"]))

    def test_low_confidence_adds_warning(self):
        extraction = {"ingredients": [], "product": {}, "specialist_types": [], "symptoms_or_risks": []}
        client = make_openai_client([extraction])
        result = analysis_service.analyze(
            {"full_text": "x", "average_confidence": 0.2},
            openai_client=client,
            citation_fetcher=lambda q: [],
        )
        self.assertTrue(any("low" in w for w in result["warnings"]))

    def test_invalid_severity_is_normalized(self):
        extraction = {
            "ingredients": [{"name_raw": "A", "name_normalized": "a", "confidence": 0.8}],
            "product": {}, "specialist_types": [], "symptoms_or_risks": [],
        }
        findings = {"summary": "s", "effects": [], "severity": "catastrophic"}
        client = make_openai_client([extraction, findings])
        result = analysis_service.analyze(
            {"full_text": "x"},
            openai_client=client,
            citation_fetcher=lambda q: [{"pmid": "1", "title": "t", "url": "u"}],
        )
        self.assertEqual(result["clinical_findings"][0]["severity"], "unknown")


if __name__ == "__main__":
    unittest.main()
