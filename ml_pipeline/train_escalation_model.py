import os
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text
from backend.database import get_engine
from backend.escalation import extract_vad_features

model_path = Path(
    os.getenv(
        "ESCALATION_MODEL_PATH",
        "/opt/factored-ai/model_assets/escalation_model.joblib",
    )
)

training_rows = int(os.getenv("ESCALATION_TRAINING_ROWS", "50000"))
random_state = 42


def load_training_rows():
    """Load historical transcript text and the real escalation outcome from RDS.

    Parameters
    ----------
    None.

    Returns
    -------
    pandas.DataFrame
        Historical text, language, and was_escalated label.
    """
    query = text(
        """
        SELECT
        COALESCE(NULLIF(BTRIM(t.customer_text), ''), t.full_text) AS customer_text,
        LOWER(COALESCE(NULLIF(t.detected_language, ''), 'es')) AS detected_language,
        i.was_escalated
        FROM call_transcripts t
        JOIN call_center_interactions i
        ON i.interaction_id = t.interaction_id
        WHERE COALESCE(NULLIF(BTRIM(t.customer_text), ''), BTRIM(t.full_text)) IS NOT NULL
        AND i.was_escalated IS NOT NULL
        ORDER BY RANDOM()
        LIMIT :training_rows
        """
    )

    return pd.read_sql(
        query,
        get_engine(),
        params={"training_rows": training_rows},
    )


def build_feature_matrix(frame):
    """Extract VAD-style features from historical sanitized-language text.

    Parameters
    ----------
    frame : pandas.DataFrame
        Historical transcript rows.

    Returns
    -------
    tuple
        X feature matrix and y binary target array.
    """
    feature_rows = []

    for row in frame.itertuples(index=False):
        language = row.detected_language

        if language not in {"en", "es", "pt"}:
            language = "es"

        features = extract_vad_features(
            text=str(row.customer_text),
            language=language,
        )

        feature_rows.append(
            [
                features["valence"],
                features["arousal"],
                features["dominance"],
            ]
        )

    x = np.asarray(feature_rows, dtype=float)
    y = frame["was_escalated"].astype(int).to_numpy()

    return x, y


def train_and_save_model():
    """Train, validate, and persist the Logistic Regression escalation model.

    Parameters
    ----------
    None.

    Returns
    -------
    dict
        Training summary and saved model path.
    """
    frame = load_training_rows()

    if frame.empty:
        raise RuntimeError("No historical escalation training rows were found.")

    x, y = build_feature_matrix(frame)

    if len(np.unique(y)) < 2:
        raise RuntimeError("Training data contains only one escalation class.")

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.20,
        random_state=random_state,
        stratify=y,
    )

    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "logistic_regression",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=random_state,
                ),
            ),
        ]
    )

    model.fit(x_train, y_train)

    probabilities = model.predict_proba(x_test)[:, 1]

    validation_roc_auc = float(
        roc_auc_score(y_test, probabilities)
    )

    artifact = {
        "model": model,
        "feature_names": ["valence", "arousal", "dominance"],
        "validation_roc_auc": validation_roc_auc,
        "training_rows": int(len(frame)),
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    model_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(
        artifact,
        model_path,
    )

    return {
        "model_path": str(model_path),
        "training_rows": int(len(frame)),
        "validation_roc_auc": validation_roc_auc,
    }


def main():
    """Train the escalation model and print the resulting artifact metadata.

    Parameters
    ----------
    None.

    Returns
    -------
    None.
    """
    print(train_and_save_model())


if __name__ == "__main__":
    main()
