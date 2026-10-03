import os
from functools import lru_cache
from pathlib import Path

import joblib

from backend.vad import extract_vad


model_path = Path(
    os.getenv(
        "ESCALATION_MODEL_PATH",
        "/opt/factored-ai/model_assets/escalation_model.joblib",
    )
)


@lru_cache(maxsize=1)
def _load_model():
    """Load the trained escalation model."""

    if not model_path.exists():
        raise RuntimeError(f"Escalation model not found: {model_path}")

    bundle = joblib.load(model_path)

    if "model" not in bundle:
        raise RuntimeError("Escalation model artifact is invalid")

    return bundle["model"]


def predict_escalation(text):
    """Predict escalation from current sanitized customer text."""

    vad = extract_vad(text)
    model = _load_model()
    feature_row = [[
        vad["valence"],
        vad["arousal"],
        vad["dominance"],
    ]]
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

    return {
        "valence": vad["valence"],
        "arousal": vad["arousal"],
        "dominance": vad["dominance"],
        "escalation_probability": float(probabilities[positive_index]),
        "requires_human_review": bool(model.predict(feature_row)[0]),
    }
