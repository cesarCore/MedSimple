"""PubMed E-utilities client: esearch + esummary, returns [{pmid,title,url}]."""

import logging

import requests

logger = logging.getLogger(__name__)

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
ARTICLE_URL_TEMPLATE = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


def fetch_citations(query, api_key=None, max_results=3, http_get=None):
    """Return up to `max_results` citations for `query` from PubMed.

    Each citation is `{pmid, title, url}`. Errors return an empty list — we
    never raise, because missing citations must not abort the analysis call.
    `http_get` is injectable for tests.
    """
    http_get = http_get or requests.get
    query = (query or "").strip()
    if not query:
        return []

    try:
        pmids = _esearch(query, api_key, max_results, http_get)
        if not pmids:
            return []
        return _esummary(pmids, api_key, http_get)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("PubMed fetch failed for %r: %s", query, exc)
        return []


def _esearch(query, api_key, max_results, http_get):
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
        "sort": "relevance",
    }
    if api_key:
        params["api_key"] = api_key

    response = http_get(ESEARCH_URL, params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()
    return payload.get("esearchresult", {}).get("idlist", []) or []


def _esummary(pmids, api_key, http_get):
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }
    if api_key:
        params["api_key"] = api_key

    response = http_get(ESUMMARY_URL, params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result", {})

    citations = []
    for pmid in pmids:
        record = result.get(pmid)
        if not record:
            continue
        title = record.get("title") or "Untitled PubMed record"
        citations.append({
            "pmid": pmid,
            "title": title,
            "url": ARTICLE_URL_TEMPLATE.format(pmid=pmid),
        })
    return citations
