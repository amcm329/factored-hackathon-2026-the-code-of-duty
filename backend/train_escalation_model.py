import os
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression

from backend.database import get_engine
from backend.vad import extract_vad


model_path = Path(
    os.getenv(
        "ESCALATION_MODEL_PATH",
        "/opt/factored-ai/model_assets/escalation_model.joblib",
    )
)
read_chunk_size = 2000


def build_training_rows():
    """Create VAD features from historical interactions and escalation labels."""

    query = """
        SELECT
            COALESCE(NULLIF(BTRIM(ct.customer_text), ''), ct.full_text) AS customer_text,
            cci.was_escalated
        FROM call_transcripts ct
        INNER JOIN call_center_interactions cci
            ON cci.interaction_id = ct.interaction_id
        WHERE COALESCE(NULLIF(BTRIM(ct.customer_text), ''), BTRIM(ct.full_text)) <> ''
          AND cci.was_escalated IS NOT NULL
    """
    features = []
    labels = []

    for chunk in pd.read_sql(
        query,
        get_engine(),
        chunksize=read_chunk_size,
    ):
        for row in chunk.itertuples(index=False):
            try:
                vad = extract_vad(str(row.customer_text))
            except ValueError:
                continue

            features.append(
                [
                    vad["valence"],
                    vad["arousal"],
                    vad["dominance"],
                ]
            )
            labels.append(bool(row.was_escalated))

    return features, labels


def train_escalation_model():
    """Train and save the Logistic Regression escalation model."""

    features, labels = build_training_rows()

    if not features:
        raise RuntimeError("No historical rows produced usable VAD features")

    if len(set(labels)) < 2:
        raise RuntimeError("Escalation training data contains only one target class")

    model = LogisticRegression()
    model.fit(features, labels)
    model_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    joblib.dump(
        {
            "model": model,
            "features": ["valence", "arousal", "dominance"],
        },
        model_path,
    )

    return {
        "model_path": str(model_path),
        "training_rows": len(features),
    }


def main():
    """Train the escalation model and print the result."""

    print(train_escalation_model())


if __name__ == "__main__":
    main()
