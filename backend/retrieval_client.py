import os

import requests


retrieval_base_url = os.getenv("RETRIEVAL_BASE_URL", "").rstrip("/")
retrieval_timeout_seconds = 120


def _post(path, payload):
    """Send one private request from Chat EC2 to Retrieval EC2."""

    if not retrieval_base_url:
        raise RuntimeError("RETRIEVAL_BASE_URL is not configured")

    response = requests.post(
        f"{retrieval_base_url}{path}",
        json=payload,
        timeout=retrieval_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def search_similar_cases_retrieval(text, country, k=5):
    """Run country-aware E5 and FAISS search on Retrieval EC2."""

    return _post(
        "/internal/retrieval/search",
        {
            "text": text,
            "country": country,
            "k": k,
        },
    )["matches"]
