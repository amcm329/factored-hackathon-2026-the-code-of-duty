import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import recall_score, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import text

from backend.database import get_engine
from backend.metrics import publish_escalation_recall
from backend.secrets import get_dispute_policy_config
from backend.vad import extract_vad


model_path = Path(
    os.getenv(
        "ESCALATION_MODEL_PATH",
        "/opt/factored-ai/model_assets/escalation_model.joblib",
    )
)
random_state = 42
numeric_features = [
    "valence",
    "arousal",
    "dominance",
]
categorical_features = [
    "country",
    "segment",
]
model_features = numeric_features + categorical_features
candidate_c_values = [0.1, 1.0, 10.0]
escalation_threshold = 0.50

# The expensive VAD model runs only on a small SQL-selected sample from the
# already date-reduced RDS data. Override with ESCALATION_TRAINING_MAX_ROWS
# if a larger evaluation run is desired.
training_max_rows = int(
    os.getenv(
        "ESCALATION_TRAINING_MAX_ROWS",
        "1500",
    )
)


def load_training_rows():
    """Load a deterministic, balanced sample before any VAD inference.

    The sample is balanced across country, escalation class, and calendar year.
    Sampling happens inside PostgreSQL, so only the selected rows reach pandas
    and the expensive VAD loop.
    """

    query = text(
        """
        WITH eligible AS (
            SELECT
                t.transcript_id,
                t.customer_text,
                LOWER(
                    COALESCE(NULLIF(t.detected_language, ''), 'es')
                ) AS detected_language,
                i.interaction_date,
                i.was_escalated,
                c.country,
                c.segment,
                EXTRACT(YEAR FROM i.interaction_date)::INTEGER AS sample_year
            FROM call_transcripts t
            JOIN call_center_interactions i
              ON i.interaction_id = t.interaction_id
            JOIN customers c
              ON c.customer_id = i.customer_id
            WHERE t.customer_text IS NOT NULL
              AND BTRIM(t.customer_text) <> ''
              AND i.interaction_date IS NOT NULL
              AND i.was_escalated IS NOT NULL
              AND c.country IS NOT NULL
              AND c.segment IS NOT NULL
        ),
        ranked AS (
            SELECT
                eligible.*,
                ROW_NUMBER() OVER (
                    PARTITION BY
                        country,
                        was_escalated,
                        sample_year
                    ORDER BY md5(transcript_id)
                ) AS sample_rank
            FROM eligible
        )
        SELECT
            customer_text,
            detected_language,
            interaction_date,
            was_escalated,
            country,
            segment
        FROM ranked
        ORDER BY
            sample_rank,
            country,
            was_escalated,
            sample_year,
            md5(transcript_id)
        LIMIT :training_max_rows
        """
    )

    frame = pd.read_sql(
        query,
        get_engine(),
        params={
            "training_max_rows": training_max_rows,
        },
    )

    print(
        f"Loaded {len(frame):,} sampled training candidates "
        f"(limit={training_max_rows:,})"
    )
    return frame


def _subtract_policy_window(max_date, policy):
    """Subtract one configured calendar or business-day country window."""

    days = int(policy["days"])
    window_type = str(policy["type"]).strip().lower()

    if window_type == "calendar_days":
        return max_date - pd.Timedelta(days=days)

    if window_type == "business_days":
        return max_date - BDay(days)

    raise RuntimeError(
        f"Unsupported dispute policy window type: {window_type}"
    )


def _country_cutoffs(frame):
    """Calculate dynamic country MIN, MAX, and temporal cutoff dates."""

    policy_config = get_dispute_policy_config()
    normalized_policy = {
        str(country).strip().casefold(): value
        for country, value in policy_config.items()
    }
    cutoffs = {}

    for country, country_frame in frame.groupby("country", sort=True):
        policy = normalized_policy.get(
            str(country).strip().casefold()
        )

        if policy is None:
            raise RuntimeError(
                f"No dispute policy window configured for country: {country}"
            )

        minimum_date = country_frame["interaction_date"].min()
        maximum_date = country_frame["interaction_date"].max()
        cutoff_date = _subtract_policy_window(
            maximum_date,
            policy,
        )
        cutoffs[country] = {
            "minimum_date": minimum_date,
            "maximum_date": maximum_date,
            "cutoff_date": cutoff_date,
            "days": int(policy["days"]),
            "type": str(policy["type"]),
        }

    return cutoffs


def _add_engineered_features(frame):
    """Create VAD features only for the reduced SQL sample."""

    result = frame.copy()
    vad_rows = []
    vad_cache = {}
    total_rows = len(result)

    for index, row in enumerate(
        result.itertuples(index=False),
        start=1,
    ):
        language = row.detected_language

        if language not in {"en", "es", "pt"}:
            language = "es"

        customer_text = str(row.customer_text)
        cache_key = (language, customer_text)

        if cache_key not in vad_cache:
            vad_cache[cache_key] = extract_vad(
                customer_text,
                language,
            )

        vad_rows.append(vad_cache[cache_key])

        if index % 250 == 0 or index == total_rows:
            print(
                f"VAD progress: {index:,}/{total_rows:,}"
            )

    result["valence"] = [
        row["valence"]
        for row in vad_rows
    ]
    result["arousal"] = [
        row["arousal"]
        for row in vad_rows
    ]
    result["dominance"] = [
        row["dominance"]
        for row in vad_rows
    ]

    return result


def _split_temporally(frame, cutoffs):
    """Split each country into historical training and recent held-out rows."""

    training_parts = []
    test_parts = []

    for country, country_frame in frame.groupby(
        "country",
        sort=True,
    ):
        cutoff = cutoffs[country]["cutoff_date"]
        training_parts.append(
            country_frame[
                country_frame["interaction_date"] < cutoff
            ]
        )
        test_parts.append(
            country_frame[
                country_frame["interaction_date"] >= cutoff
            ]
        )

    training_frame = pd.concat(
        training_parts,
        ignore_index=True,
    )
    test_frame = pd.concat(
        test_parts,
        ignore_index=True,
    )
    training_frame = training_frame.sort_values(
        "interaction_date"
    ).reset_index(drop=True)
    test_frame = test_frame.sort_values(
        "interaction_date"
    ).reset_index(drop=True)

    if training_frame.empty:
        raise RuntimeError(
            "Temporal training split contains no rows"
        )

    if test_frame.empty:
        raise RuntimeError(
            "Temporal held-out split contains no rows"
        )

    return training_frame, test_frame


def _build_pipeline(c_value):
    """Build one preprocessing and Logistic Regression pipeline."""

    preprocessor = ColumnTransformer(
        [
            (
                "numeric",
                StandardScaler(),
                numeric_features,
            ),
            (
                "categorical",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=False,
                ),
                categorical_features,
            ),
        ],
        remainder="drop",
    )

    return Pipeline(
        [
            ("preprocessor", preprocessor),
            (
                "logistic_regression",
                LogisticRegression(
                    C=float(c_value),
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=random_state,
                ),
            ),
        ]
    )


def _select_best_configuration(training_frame):
    """Select Logistic Regression regularization using time-aware folds."""

    splitter = TimeSeriesSplit(n_splits=5)
    x = training_frame[model_features]
    y = training_frame["was_escalated"].astype(int).to_numpy()
    results = []

    for c_value in candidate_c_values:
        fold_recalls = []
        fold_roc_aucs = []

        for train_indexes, validation_indexes in splitter.split(x):
            y_train = y[train_indexes]
            y_validation = y[validation_indexes]

            if len(np.unique(y_train)) < 2:
                continue

            model = _build_pipeline(c_value)
            model.fit(
                x.iloc[train_indexes],
                y_train,
            )
            probabilities = model.predict_proba(
                x.iloc[validation_indexes]
            )[:, 1]
            predictions = (
                probabilities >= escalation_threshold
            ).astype(int)
            fold_recalls.append(
                float(
                    recall_score(
                        y_validation,
                        predictions,
                        zero_division=0,
                    )
                )
            )

            if len(np.unique(y_validation)) >= 2:
                fold_roc_aucs.append(
                    float(
                        roc_auc_score(
                            y_validation,
                            probabilities,
                        )
                    )
                )

        if not fold_recalls:
            continue

        results.append(
            {
                "C": float(c_value),
                "mean_recall": float(np.mean(fold_recalls)),
                "mean_roc_auc": (
                    float(np.mean(fold_roc_aucs))
                    if fold_roc_aucs
                    else None
                ),
                "valid_folds": int(len(fold_recalls)),
            }
        )

    if not results:
        raise RuntimeError(
            "Time-aware cross-validation could not evaluate any model configuration"
        )

    best = max(
        results,
        key=lambda item: (
            item["mean_recall"],
            (
                item["mean_roc_auc"]
                if item["mean_roc_auc"] is not None
                else -1.0
            ),
        ),
    )
    return best, results


def _feature_importance(model):
    """Return signed and absolute Logistic Regression coefficient importance."""

    feature_names = model.named_steps[
        "preprocessor"
    ].get_feature_names_out()
    coefficients = model.named_steps[
        "logistic_regression"
    ].coef_[0]
    importance = []

    for feature_name, coefficient in zip(
        feature_names,
        coefficients,
    ):
        clean_name = str(feature_name).split("__", 1)[-1]
        importance.append(
            {
                "feature": clean_name,
                "coefficient": float(coefficient),
                "absolute_importance": float(
                    abs(coefficient)
                ),
            }
        )

    return sorted(
        importance,
        key=lambda item: item["absolute_importance"],
        reverse=True,
    )


def _serialize_cutoffs(cutoffs):
    """Convert timestamp cutoff metadata to joblib-friendly strings."""

    return {
        country: {
            "minimum_date": values["minimum_date"].isoformat(),
            "maximum_date": values["maximum_date"].isoformat(),
            "cutoff_date": values["cutoff_date"].isoformat(),
            "days": values["days"],
            "type": values["type"],
        }
        for country, values in cutoffs.items()
    }


def train_and_save_model():
    """Train, validate, and persist the temporal escalation model pipeline."""

    frame = load_training_rows()

    if frame.empty:
        raise RuntimeError(
            "No historical escalation training rows were found"
        )

    frame["interaction_date"] = pd.to_datetime(
        frame["interaction_date"],
        errors="coerce",
    )
    frame = frame.dropna(
        subset=[
            "interaction_date",
            "country",
            "segment",
            "customer_text",
            "was_escalated",
        ]
    ).reset_index(drop=True)

    if frame.empty:
        raise RuntimeError(
            "No valid escalation rows remained after validation"
        )

    cutoffs = _country_cutoffs(frame)
    frame = _add_engineered_features(frame)
    training_frame, test_frame = _split_temporally(
        frame,
        cutoffs,
    )

    y_train = training_frame[
        "was_escalated"
    ].astype(int).to_numpy()
    y_test = test_frame[
        "was_escalated"
    ].astype(int).to_numpy()

    if len(np.unique(y_train)) < 2:
        raise RuntimeError(
            "Training data contains only one escalation class"
        )

    best_configuration, cv_results = _select_best_configuration(
        training_frame
    )
    model = _build_pipeline(
        best_configuration["C"]
    )
    model.fit(
        training_frame[model_features],
        y_train,
    )

    test_probabilities = model.predict_proba(
        test_frame[model_features]
    )[:, 1]
    test_predictions = (
        test_probabilities >= escalation_threshold
    ).astype(int)
    validation_recall = float(
        recall_score(
            y_test,
            test_predictions,
            zero_division=0,
        )
    )
    validation_roc_auc = (
        float(
            roc_auc_score(
                y_test,
                test_probabilities,
            )
        )
        if len(np.unique(y_test)) >= 2
        else None
    )
    importance = _feature_importance(model)
    artifact = {
        "model": model,
        "raw_feature_names": model_features,
        "feature_importance": importance,
        "best_logistic_regression_C": best_configuration["C"],
        "escalation_threshold": escalation_threshold,
        "cross_validation": cv_results,
        "validation_roc_auc": validation_roc_auc,
        "validation_recall": validation_recall,
        "training_source_sample_limit": training_max_rows,
        "training_rows": int(len(training_frame)),
        "held_out_rows": int(len(test_frame)),
        "country_cutoffs": _serialize_cutoffs(cutoffs),
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
    publish_escalation_recall(
        validation_recall
    )

    return {
        "model_path": str(model_path),
        "training_source_sample_limit": training_max_rows,
        "training_rows": int(len(training_frame)),
        "held_out_rows": int(len(test_frame)),
        "best_logistic_regression_C": best_configuration["C"],
        "escalation_threshold": escalation_threshold,
        "validation_roc_auc": validation_roc_auc,
        "validation_recall": validation_recall,
        "country_cutoffs": artifact["country_cutoffs"],
        "feature_importance": importance,
    }


def main():
    """Train the escalation model and print the resulting artifact metadata."""

    print(train_and_save_model())


if __name__ == "__main__":
    main()
