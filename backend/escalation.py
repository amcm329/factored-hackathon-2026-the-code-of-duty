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


def _build_live_feature_row(text, language, country, segment):
    """Build one live feature row using only stable prediction-time inputs."""

    vad = extract_vad(text, language)
    return pd.DataFrame(
        [
            {
                "valence": vad["valence"],
                "arousal": vad["arousal"],
                "dominance": vad["dominance"],
                "country": country,
                "segment": segment,
            }
        ]
    )


def predict_escalation(text, language="es", country="", segment=""):
    """Predict escalation from current customer text and authenticated context."""

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
        "escalation_probability": probability,
        "requires_human_review": probability >= threshold,
    }
