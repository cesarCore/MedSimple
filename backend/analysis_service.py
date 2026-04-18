"""Medication analysis agent: OpenAI extraction + PubMed citations.

Strict rule: `clinical_findings[].citations` must only contain PubMed records
actually returned by `pubmed_service.fetch_citations`. The LLM is never
asked to produce PMIDs — it only produces summaries and effects, and we
attach citations retrieved from PubMed.
"""

import json
import logging
from datetime import datetime, timezone

from backend.pubmed_service import fetch_citations

try:
    from backend.specialist_service import infer_specialist_types as _keyword_infer
except ModuleNotFoundError:
    from specialist_service import infer_specialist_types as _keyword_infer

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
MAX_INGREDIENTS_FOR_CITATIONS = 5

EXTRACTION_SYSTEM_PROMPT = """You extract medication data from noisy OCR text
of prescription / supplement / OTC bottles. Return a single JSON object with
exactly this shape — no prose, no markdown:

{
  "product": {
    "raw_name": string or null,
    "normalized_name": string or null,
    "product_type": "prescription" | "otc" | "supplement" | "unknown",
    "dosage_text": string or null
  },
  "ingredients": [
    {"name_raw": string, "name_normalized": string, "confidence": number 0..1}
  ],
  "specialist_types": [string],
  "symptoms_or_risks": [string]
}

Rules:
- Only include ingredients you can actually see in the text.
- `specialist_types` should be medical specialist labels (e.g.
  "cardiologist", "endocrinologist", "pharmacy") relevant to the ingredients.
- Do not invent PMIDs, studies, or URLs.
- If the text is too garbled to extract anything, return empty arrays.
"""

FINDINGS_SYSTEM_PROMPT = """You write short, factual summaries of clinical
effects for a single medication ingredient, grounded ONLY in the PubMed
titles provided. Return a single JSON object with exactly this shape:

{
  "summary": string,
  "effects": [string],
  "severity": "low" | "moderate" | "high" | "unknown"
}

Rules:
- If no PubMed titles are provided, set summary to a single sentence noting
  the lack of retrieved evidence and severity to "unknown".
- Do not invent study results. Only claim what is plausibly supported by
  the titles listed.
- Keep `summary` under 240 characters.
"""


def analyze(ocr_payload, user_context=None, openai_client=None,
            citation_fetcher=None, model=DEFAULT_MODEL, pubmed_api_key=None):
    """Run the Analysis agent.

    `ocr_payload` is the OCR-agent output (at least `full_text`).
    `openai_client` is injectable (duck-typed to the v1 SDK). Default lazy-loads.
    `citation_fetcher(query) -> [{pmid,title,url}]` is injectable for tests.
    """
    citation_fetcher = citation_fetcher or (
        lambda q: fetch_citations(q, api_key=pubmed_api_key)
    )
    openai_client = openai_client or _default_openai_client()

    full_text = (ocr_payload or {}).get("full_text", "") or ""
    average_confidence = float((ocr_payload or {}).get("average_confidence", 0.0))
    warnings = []

    extraction = _extract_product_and_ingredients(
        openai_client, model, full_text, user_context, warnings
    )

    clinical_findings = []
    for ingredient in extraction["ingredients"][:MAX_INGREDIENTS_FOR_CITATIONS]:
        name = ingredient["name_normalized"] or ingredient["name_raw"]
        query = f"{name} side effects"
        citations = citation_fetcher(query)
        finding = _summarize_ingredient(
            openai_client, model, name, citations, warnings
        )
        clinical_findings.append({
            "ingredient": name,
            "summary": finding["summary"],
            "effects": finding["effects"],
            "severity": finding["severity"],
            "specialist_types": extraction["specialist_types"],
            "citations": citations,
        })
        ingredient["evidence_query"] = query

    specialist_types = extraction["specialist_types"] or _keyword_infer(full_text)

    if average_confidence and average_confidence < 0.5:
        warnings.append(
            f"OCR average_confidence {average_confidence:.2f} is low; "
            "extraction may be unreliable."
        )

    return {
        "status": "success",
        "product": extraction["product"],
        "ingredients": extraction["ingredients"],
        "clinical_findings": clinical_findings,
        "specialist_recommendation_basis": {
            "symptoms_or_risks": extraction["symptoms_or_risks"],
            "specialist_types": specialist_types,
        },
        "warnings": warnings,
        "metadata": {
            "model": model,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def _extract_product_and_ingredients(client, model, full_text, user_context, warnings):
    focus = (user_context or {}).get("focus", "full")
    notes = (user_context or {}).get("notes") or ""
    user_prompt = (
        f"Focus: {focus}\n"
        f"Notes: {notes}\n\n"
        f"OCR text:\n{full_text}\n"
    )
    try:
        payload = _chat_json(client, model, EXTRACTION_SYSTEM_PROMPT, user_prompt)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("OpenAI extraction failed: %s", exc)
        warnings.append(f"extraction failed: {exc}")
        payload = {}

    product = payload.get("product") or {}
    ingredients = payload.get("ingredients") or []
    normalized_ingredients = []
    for entry in ingredients:
        name_raw = (entry.get("name_raw") or "").strip()
        name_norm = (entry.get("name_normalized") or name_raw).strip()
        if not name_raw and not name_norm:
            continue
        try:
            confidence = float(entry.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        normalized_ingredients.append({
            "name_raw": name_raw or name_norm,
            "name_normalized": name_norm or name_raw,
            "confidence": max(0.0, min(1.0, confidence)),
            "evidence_query": entry.get("evidence_query") or "",
        })

    return {
        "product": {
            "raw_name": product.get("raw_name"),
            "normalized_name": product.get("normalized_name"),
            "product_type": product.get("product_type") or "unknown",
            "dosage_text": product.get("dosage_text"),
        },
        "ingredients": normalized_ingredients,
        "specialist_types": [s for s in (payload.get("specialist_types") or []) if s],
        "symptoms_or_risks": [s for s in (payload.get("symptoms_or_risks") or []) if s],
    }


def _summarize_ingredient(client, model, ingredient, citations, warnings):
    if not citations:
        return {
            "summary": f"No PubMed evidence retrieved for {ingredient}.",
            "effects": [],
            "severity": "unknown",
        }

    bullet_titles = "\n".join(f"- PMID {c['pmid']}: {c['title']}" for c in citations)
    user_prompt = (
        f"Ingredient: {ingredient}\n"
        f"PubMed titles:\n{bullet_titles}\n"
    )
    try:
        payload = _chat_json(client, model, FINDINGS_SYSTEM_PROMPT, user_prompt)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("OpenAI findings call failed for %s: %s", ingredient, exc)
        warnings.append(f"findings failed for {ingredient}: {exc}")
        return {
            "summary": f"Evidence retrieved but summary unavailable for {ingredient}.",
            "effects": [],
            "severity": "unknown",
        }

    severity = payload.get("severity")
    if severity not in {"low", "moderate", "high", "unknown"}:
        severity = "unknown"
    return {
        "summary": (payload.get("summary") or "").strip(),
        "effects": [e for e in (payload.get("effects") or []) if e],
        "severity": severity,
    }


def _chat_json(client, model, system_prompt, user_prompt):
    """Call chat.completions with JSON mode and parse the result."""
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def _default_openai_client():
    """Lazy-import the OpenAI SDK so tests can run without it installed."""
    try:
        from openai import OpenAI  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise RuntimeError("openai package is required for analysis") from exc
    return OpenAI()
