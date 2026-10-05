import os
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

from backend.vad import extract_vad


model_path = Path(
    os.getenv(
        "ESCALATION_MODEL_PATH",
        "/opt/factored-ai/model_assets/escalation_model.joblib",
    )
)


@lru_cache(maxsize=1)
def _load_model_artifact():
    """Load the trained escalation model artifact."""

    if not model_path.exists():
        raise RuntimeError(f"Escalation model not found: {model_path}")

    artifact = joblib.load(model_path)

    if "model" not in artifact:
        raise RuntimeError("Escalation model artifact is invalid")

    return artifact


def _categorical(value):
    value = str(value or "").strip()
    return value if value else "UNKNOWN"


def _numeric(value):
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _build_live_feature_row(text, language, country, segment, transaction=None):
    """Build one prediction row using text, customer context, and the verified selected transaction."""

    transaction = transaction or {}
    vad = extract_vad(text, language)
    transaction_linked = 1.0 if transaction.get("transaction_id") else 0.0

    return pd.DataFrame(
        [
            {
                "valence": vad["valence"],
                "arousal": vad["arousal"],
                "dominance": vad["dominance"],
                "transaction_linked": transaction_linked,
                "amount_usd": _numeric(transaction.get("amount_usd")),
                "fraud_score": _numeric(transaction.get("fraud_score")),
                "country": _categorical(country),
                "segment": _categorical(segment),
                "transaction_type": _categorical(transaction.get("transaction_type")),
                "transaction_category": _categorical(transaction.get("transaction_category")),
                "channel": _categorical(transaction.get("channel")),
                "transaction_status": _categorical(transaction.get("transaction_status")),
                "merchant_category": _categorical(transaction.get("merchant_category")),
                "is_fraud": _categorical(transaction.get("is_fraud")),
            }
        ]
    )


def predict_escalation(text, language="es", country="", segment="", transaction=None):
    """Predict escalation from current text, authenticated context, and verified transaction data."""

    if not country:
        raise ValueError("country is required")

    if not segment:
        raise ValueError("segment is required")

    artifact = _load_model_artifact()
    model = artifact["model"]
    feature_row = _build_live_feature_row(
        text=text,
        language=language,
        country=country,
        segment=segment,
        transaction=transaction,
    )
    probabilities = model.predict_proba(feature_row)[0]
    classes = list(model.classes_)
    positive_index = next(
        (
            index
            for index, value in enumerate(classes)
            if value is True or value == 1
        ),
        None,
    )

    if positive_index is None:
        raise RuntimeError("Escalation model does not contain a positive class")

    probability = float(probabilities[positive_index])
    threshold = float(artifact.get("escalation_threshold", 0.50))
    return {
        "valence": float(feature_row.iloc[0]["valence"]),
        "arousal": float(feature_row.iloc[0]["arousal"]),
        "dominance": float(feature_row.iloc[0]["dominance"]),
        "transaction_linked": bool(feature_row.iloc[0]["transaction_linked"]),
        "escalation_probability": probability,
        "requires_human_review": probability >= threshold,
    }
