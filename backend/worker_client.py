import os

import requests


worker_base_url = os.getenv("WORKER_BASE_URL", "").rstrip("/")
worker_timeout_seconds = 120


def _post(path, payload):
    """Send one private request from Chat EC2 to Worker EC2."""

    if not worker_base_url:
        raise RuntimeError("WORKER_BASE_URL is not configured")

    response = requests.post(
        f"{worker_base_url}{path}",
        json=payload,
        timeout=worker_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def read_sanitized_evidence(evidence_id, customer_id):
    """Read sanitized evidence through Worker EC2."""

    return _post(
        "/internal/evidence/read",
        {
            "evidence_id": evidence_id,
            "customer_id": customer_id,
        },
    )["text"]


def predict_escalation_worker(text, language, country, segment, transaction=None):
    """Run VAD and Logistic Regression inference on Worker EC2."""

    return _post(
        "/internal/escalation/predict",
        {
            "text": text,
            "language": language,
            "country": country,
            "segment": segment,
            "transaction": transaction or {},
        },
    )
