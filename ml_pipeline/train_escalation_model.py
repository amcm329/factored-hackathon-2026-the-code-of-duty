import json
import os
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
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
evaluation_path = Path(
    os.getenv(
        "ESCALATION_EVALUATION_PATH",
        str(model_path.with_name("escalation_evaluation.json")),
    )
)
random_state = 42
numeric_features = [
    "valence",
    "arousal",
    "dominance",
    "transaction_linked",
    "amount_usd",
    "fraud_score",
]
categorical_features = [
    "country",
    "segment",
    "transaction_type",
    "transaction_category",
    "channel",
    "transaction_status",
    "merchant_category",
    "is_fraud",
]
model_features = numeric_features + categorical_features
candidate_c_values = [0.1, 1.0, 10.0]
escalation_threshold = 0.50
calendar_sampling_days = 5

# VAD is expensive. SQL first selects a deterministic balanced candidate sample;
# the five-calendar-day rule is then applied before VAD inference.
training_max_rows = int(
    os.getenv(
        "ESCALATION_TRAINING_MAX_ROWS",
        "1500",
    )
)


def load_training_rows():
    """Load deterministic escalation candidates and only safe complaint->transaction matches.

    A transaction is attached to a historical interaction only when:
    - the complaint originated from that interaction;
    - customer, product, amount and currency match; and
    - exactly one transaction satisfies the conditions before complaint creation.

    Ambiguous historical transaction matches are deliberately left unlinked.
    """

    query = text(
        """
        WITH eligible AS (
            SELECT
                t.transcript_id,
                t.interaction_id,
                t.customer_id,
                t.customer_text,
                LOWER(COALESCE(NULLIF(t.detected_language, ''), 'es')) AS detected_language,
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
                    PARTITION BY country, was_escalated, sample_year
                    ORDER BY md5(transcript_id)
                ) AS sample_rank
            FROM eligible
        ),
        sampled AS (
            SELECT *
            FROM ranked
            ORDER BY
                sample_rank,
                country,
                was_escalated,
                sample_year,
                md5(transcript_id)
            LIMIT :training_max_rows
        ),
        with_complaint AS (
            SELECT
                s.*,
                cp.complaint_id,
                cp.creation_date AS complaint_creation_date,
                cp.affected_product_id,
                cp.claimed_amount,
                cp.currency AS complaint_currency
            FROM sampled s
            LEFT JOIN LATERAL (
                SELECT
                    cpl.complaint_id,
                    cpl.creation_date,
                    cpl.affected_product_id,
                    cpl.claimed_amount,
                    cpl.currency
                FROM complaints cpl
                WHERE cpl.origin_interaction_id = s.interaction_id
                  AND cpl.customer_id = s.customer_id
                ORDER BY cpl.creation_date ASC, cpl.complaint_id
                LIMIT 1
            ) cp ON TRUE
        )
        SELECT
            w.customer_text,
            w.detected_language,
            w.interaction_date,
            w.was_escalated,
            w.country,
            w.segment,
            COALESCE(tx.transaction_linked, 0) AS transaction_linked,
            COALESCE(tx.amount_usd, 0.0) AS amount_usd,
            COALESCE(tx.fraud_score, 0.0) AS fraud_score,
            COALESCE(tx.transaction_type, 'UNKNOWN') AS transaction_type,
            COALESCE(tx.transaction_category, 'UNKNOWN') AS transaction_category,
            COALESCE(tx.channel, 'UNKNOWN') AS channel,
            COALESCE(tx.transaction_status, 'UNKNOWN') AS transaction_status,
            COALESCE(tx.merchant_category, 'UNKNOWN') AS merchant_category,
            COALESCE(tx.is_fraud, 'UNKNOWN') AS is_fraud
        FROM with_complaint w
        LEFT JOIN LATERAL (
            SELECT
                CASE WHEN COUNT(*) = 1 THEN 1 ELSE 0 END::INTEGER AS transaction_linked,
                CASE WHEN COUNT(*) = 1 THEN MAX(t.amount_usd) END AS amount_usd,
                CASE WHEN COUNT(*) = 1 THEN MAX(t.fraud_score) END AS fraud_score,
                CASE WHEN COUNT(*) = 1 THEN MAX(t.transaction_type) END AS transaction_type,
                CASE WHEN COUNT(*) = 1 THEN MAX(t.transaction_category) END AS transaction_category,
                CASE WHEN COUNT(*) = 1 THEN MAX(t.channel) END AS channel,
                CASE WHEN COUNT(*) = 1 THEN MAX(t.transaction_status) END AS transaction_status,
                CASE WHEN COUNT(*) = 1 THEN MAX(t.merchant_category) END AS merchant_category,
                CASE
                    WHEN COUNT(*) = 1 THEN
                        CASE WHEN BOOL_OR(t.is_fraud) THEN 'true' ELSE 'false' END
                END AS is_fraud
            FROM transactions t
            WHERE w.complaint_id IS NOT NULL
              AND w.affected_product_id IS NOT NULL
              AND w.claimed_amount IS NOT NULL
              AND w.complaint_currency IS NOT NULL
              AND t.customer_id = w.customer_id
              AND t.product_id = w.affected_product_id
              AND t.amount = w.claimed_amount
              AND t.currency = w.complaint_currency
              AND t.transaction_date <= w.complaint_creation_date
        ) tx ON TRUE
        ORDER BY w.interaction_date, w.customer_text
        """
    )

    frame = pd.read_sql(
        query,
        get_engine(),
        params={"training_max_rows": training_max_rows},
    )
    print(
        f"Loaded {len(frame):,} sampled training candidates "
        f"(limit={training_max_rows:,})"
    )
    return frame


def _normalize_country_key(value):
    normalized = unicodedata.normalize("NFKD", str(value).strip())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return without_accents.casefold()


def _subtract_policy_window(max_date, policy):
    days = int(policy["days"])
    window_type = str(policy["type"]).strip().lower()

    if window_type == "calendar_days":
        return max_date - pd.Timedelta(days=days)
    if window_type == "business_days":
        return max_date - BDay(days)
    raise RuntimeError(f"Unsupported dispute policy window type: {window_type}")


def _country_cutoffs(frame):
    policy_config = get_dispute_policy_config()
    normalized_policy = {
        _normalize_country_key(country): value
        for country, value in policy_config.items()
    }
    cutoffs = {}

    for country, country_frame in frame.groupby("country", sort=True):
        policy = normalized_policy.get(_normalize_country_key(country))
        if policy is None:
            raise RuntimeError(
                f"No dispute policy window configured for country: {country}"
            )

        minimum_date = country_frame["interaction_date"].min()
        maximum_date = country_frame["interaction_date"].max()
        cutoff_date = _subtract_policy_window(maximum_date, policy)
        cutoffs[country] = {
            "minimum_date": minimum_date,
            "maximum_date": maximum_date,
            "cutoff_date": cutoff_date,
            "days": int(policy["days"]),
            "type": str(policy["type"]),
        }

    return cutoffs


def _subsample_every_five_calendar_days(frame):
    """Keep rows occurring on every fifth calendar day from the sample's first date."""

    result = frame.copy()
    normalized_dates = result["interaction_date"].dt.normalize()
    start = normalized_dates.min()
    day_offsets = (normalized_dates - start).dt.days
    result = result[day_offsets.mod(calendar_sampling_days).eq(0)].copy()
    result = result.sort_values("interaction_date").reset_index(drop=True)
    print(
        f"Five-calendar-day subsampling: {len(frame):,} -> {len(result):,} rows "
        f"(anchor={start.date().isoformat()})"
    )
    return result


def _add_engineered_features(frame):
    result = frame.copy()
    vad_rows = []
    vad_cache = {}
    total_rows = len(result)

    for index, row in enumerate(result.itertuples(index=False), start=1):
        language = row.detected_language
        if language not in {"en", "es", "pt"}:
            language = "es"

        customer_text = str(row.customer_text)
        cache_key = (language, customer_text)
        if cache_key not in vad_cache:
            vad_cache[cache_key] = extract_vad(customer_text, language)
        vad_rows.append(vad_cache[cache_key])

        if index % 250 == 0 or index == total_rows:
            print(f"VAD progress: {index:,}/{total_rows:,}")

    result["valence"] = [row["valence"] for row in vad_rows]
    result["arousal"] = [row["arousal"] for row in vad_rows]
    result["dominance"] = [row["dominance"] for row in vad_rows]

    for column in ["amount_usd", "fraud_score", "transaction_linked"]:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    for column in categorical_features:
        result[column] = result[column].fillna("UNKNOWN").astype(str)

    return result


def _split_temporally(frame, cutoffs):
    training_parts = []
    test_parts = []

    for country, country_frame in frame.groupby("country", sort=True):
        cutoff = cutoffs[country]["cutoff_date"]
        training_parts.append(country_frame[country_frame["interaction_date"] < cutoff])
        test_parts.append(country_frame[country_frame["interaction_date"] >= cutoff])

    training_frame = pd.concat(training_parts, ignore_index=True)
    test_frame = pd.concat(test_parts, ignore_index=True)
    training_frame = training_frame.sort_values("interaction_date").reset_index(drop=True)
    test_frame = test_frame.sort_values("interaction_date").reset_index(drop=True)

    if training_frame.empty:
        raise RuntimeError("Temporal training split contains no rows")
    if test_frame.empty:
        raise RuntimeError("Temporal held-out split contains no rows")
    return training_frame, test_frame


def _build_pipeline(c_value):
    preprocessor = ColumnTransformer(
        [
            ("numeric", StandardScaler(), numeric_features),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
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
    if len(training_frame) < 12:
        raise RuntimeError("Too few training rows remain after five-day subsampling")

    n_splits = min(5, max(2, len(training_frame) // 20))
    splitter = TimeSeriesSplit(n_splits=n_splits)
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
            model.fit(x.iloc[train_indexes], y_train)
            probabilities = model.predict_proba(x.iloc[validation_indexes])[:, 1]
            predictions = (probabilities >= escalation_threshold).astype(int)
            fold_recalls.append(
                float(recall_score(y_validation, predictions, zero_division=0))
            )
            if len(np.unique(y_validation)) >= 2:
                fold_roc_aucs.append(float(roc_auc_score(y_validation, probabilities)))

        if fold_recalls:
            results.append(
                {
                    "C": float(c_value),
                    "mean_recall": float(np.mean(fold_recalls)),
                    "mean_roc_auc": (
                        float(np.mean(fold_roc_aucs)) if fold_roc_aucs else None
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
            item["mean_roc_auc"] if item["mean_roc_auc"] is not None else -1.0,
        ),
    )
    return best, results


def _feature_importance(model):
    feature_names = model.named_steps["preprocessor"].get_feature_names_out()
    coefficients = model.named_steps["logistic_regression"].coef_[0]
    importance = []

    for feature_name, coefficient in zip(feature_names, coefficients):
        clean_name = str(feature_name).split("__", 1)[-1]
        importance.append(
            {
                "feature": clean_name,
                "coefficient": float(coefficient),
                "absolute_importance": float(abs(coefficient)),
            }
        )

    return sorted(importance, key=lambda item: item["absolute_importance"], reverse=True)


def _serialize_cutoffs(cutoffs):
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


def _positive_probability(classifier, x):
    probabilities = classifier.predict_proba(x)
    classes = list(classifier.classes_)
    positive_index = next(
        (idx for idx, value in enumerate(classes) if value is True or value == 1),
        None,
    )
    if positive_index is None:
        raise RuntimeError("Classifier does not contain a positive class")
    return probabilities[:, positive_index]


def _metric_pair(y_true, probabilities):
    predictions = (probabilities >= escalation_threshold).astype(int)
    recall = float(recall_score(y_true, predictions, zero_division=0))
    auc = (
        float(roc_auc_score(y_true, probabilities))
        if len(np.unique(y_true)) >= 2
        else None
    )
    return recall, auc, predictions


def _subgroup_metrics(frame, y_true, probabilities, predictions, column):
    result = {}
    series = frame[column].fillna("UNKNOWN").astype(str).reset_index(drop=True)
    for value in sorted(series.unique()):
        mask = series.eq(value).to_numpy()
        group_y = y_true[mask]
        group_prob = probabilities[mask]
        group_pred = predictions[mask]
        result[value] = {
            "rows": int(mask.sum()),
            "positive_labels": int(group_y.sum()),
            "recall": float(recall_score(group_y, group_pred, zero_division=0)),
            "roc_auc": (
                float(roc_auc_score(group_y, group_prob))
                if len(np.unique(group_y)) >= 2
                else None
            ),
        }
    return result


def train_and_save_model():
    frame = load_training_rows()
    if frame.empty:
        raise RuntimeError("No historical escalation training rows were found")

    frame["interaction_date"] = pd.to_datetime(frame["interaction_date"], errors="coerce")
    frame = frame.dropna(
        subset=["interaction_date", "country", "segment", "customer_text", "was_escalated"]
    ).reset_index(drop=True)
    if frame.empty:
        raise RuntimeError("No valid escalation rows remained after validation")

    frame = _subsample_every_five_calendar_days(frame)
    if frame.empty:
        raise RuntimeError("No rows remained after five-calendar-day subsampling")

    cutoffs = _country_cutoffs(frame)
    frame = _add_engineered_features(frame)
    training_frame, test_frame = _split_temporally(frame, cutoffs)

    y_train = training_frame["was_escalated"].astype(int).to_numpy()
    y_test = test_frame["was_escalated"].astype(int).to_numpy()
    if len(np.unique(y_train)) < 2:
        raise RuntimeError("Training data contains only one escalation class")

    best_configuration, cv_results = _select_best_configuration(training_frame)
    model = _build_pipeline(best_configuration["C"])
    model.fit(training_frame[model_features], y_train)

    test_probabilities = _positive_probability(model, test_frame[model_features])
    validation_recall, validation_roc_auc, test_predictions = _metric_pair(
        y_test, test_probabilities
    )

    baseline = DummyClassifier(strategy="prior", random_state=random_state)
    baseline.fit(np.zeros((len(y_train), 1)), y_train)
    baseline_probabilities = _positive_probability(
        baseline, np.zeros((len(y_test), 1))
    )
    baseline_recall, baseline_roc_auc, _ = _metric_pair(y_test, baseline_probabilities)

    missed_escalations = int(((y_test == 1) & (test_predictions == 0)).sum())
    unnecessary_escalations = int(((y_test == 0) & (test_predictions == 1)).sum())

    importance = _feature_importance(model)
    trained_at = datetime.now(timezone.utc).isoformat()
    transaction_link_rate = float(frame["transaction_linked"].mean()) if len(frame) else 0.0

    evaluation = {
        "trained_at_utc": trained_at,
        "sampling": {
            "rule": "every_5_calendar_days",
            "days": calendar_sampling_days,
            "source_sample_limit": training_max_rows,
            "rows_after_sampling": int(len(frame)),
        },
        "model": {
            "type": "LogisticRegression",
            "recall": validation_recall,
            "roc_auc": validation_roc_auc,
            "threshold": escalation_threshold,
            "best_C": best_configuration["C"],
        },
        "baseline": {
            "type": "DummyClassifier(strategy=prior)",
            "recall": baseline_recall,
            "roc_auc": baseline_roc_auc,
        },
        "comparison_to_baseline": {
            "recall_delta": validation_recall - baseline_recall,
            "roc_auc_delta": (
                validation_roc_auc - baseline_roc_auc
                if validation_roc_auc is not None and baseline_roc_auc is not None
                else None
            ),
        },
        "escalation_errors": {
            "missed": missed_escalations,
            "unnecessary": unnecessary_escalations,
        },
        "rows": {
            "training": int(len(training_frame)),
            "held_out": int(len(test_frame)),
        },
        "transaction_linkage": {
            "method": "customer+product+amount+currency+transaction_date<=complaint_creation; exactly_one_candidate",
            "linked_rate": transaction_link_rate,
            "linked_rows": int(frame["transaction_linked"].sum()),
        },
        "subgroups": {
            "detected_language": _subgroup_metrics(
                test_frame, y_test, test_probabilities, test_predictions, "detected_language"
            ),
            "segment": _subgroup_metrics(
                test_frame, y_test, test_probabilities, test_predictions, "segment"
            ),
            "country": _subgroup_metrics(
                test_frame, y_test, test_probabilities, test_predictions, "country"
            ),
        },
        "country_cutoffs": _serialize_cutoffs(cutoffs),
        "cross_validation": cv_results,
        "feature_importance": importance,
    }

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
        "country_cutoffs": evaluation["country_cutoffs"],
        "sampling_days": calendar_sampling_days,
        "transaction_link_rate": transaction_link_rate,
        "trained_at_utc": trained_at,
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_path)
    evaluation_path.parent.mkdir(parents=True, exist_ok=True)
    evaluation_path.write_text(json.dumps(evaluation, indent=2, ensure_ascii=False))
    publish_escalation_recall(validation_recall)

    return {
        "model_path": str(model_path),
        "evaluation_path": str(evaluation_path),
        **evaluation,
    }


def main():
    print(json.dumps(train_and_save_model(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
