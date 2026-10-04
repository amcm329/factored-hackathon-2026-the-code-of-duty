import json
import os
from pathlib import Path

import boto3
import faiss
import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay
from sentence_transformers import SentenceTransformer

from backend.database import get_engine
from backend.language import detect_language
from backend.privacy import sanitize_text
from backend.secrets import get_dispute_policy_config


model_name = os.getenv(
    "E5_MODEL",
    "intfloat/multilingual-e5-base",
)
asset_dir = Path(
    os.getenv(
        "RETRIEVAL_ASSET_DIR",
        "/opt/factored-ai/retrieval_assets",
    )
)
index_path = asset_dir / "complaints.faiss"
mapping_path = asset_dir / "complaint_ids.json"
read_chunk_size = 2000
embedding_batch_size = 32
fallback_language = os.getenv("RETRIEVAL_FALLBACK_LANGUAGE", "es")
aws_region = os.getenv("AWS_REGION", "us-east-1")
runtime_asset_bucket = os.getenv("RUNTIME_ASSET_BUCKET", "").strip()
retrieval_asset_prefix = os.getenv(
    "RETRIEVAL_ASSET_PREFIX",
    "runtime-assets/retrieval",
).strip("/")


def publish_retrieval_assets():
    """Publish FAISS runtime artifacts for Retrieval EC2."""

    if not runtime_asset_bucket:
        raise RuntimeError("RUNTIME_ASSET_BUCKET is not configured")

    s3 = boto3.client(
        "s3",
        region_name=aws_region,
    )
    index_key = f"{retrieval_asset_prefix}/complaints.faiss"
    mapping_key = f"{retrieval_asset_prefix}/complaint_ids.json"

    s3.upload_file(
        str(index_path),
        runtime_asset_bucket,
        index_key,
    )
    s3.upload_file(
        str(mapping_path),
        runtime_asset_bucket,
        mapping_key,
    )

    return {
        "asset_bucket": runtime_asset_bucket,
        "index_key": index_key,
        "mapping_key": mapping_key,
    }


def _subtract_policy_window(max_date, policy):
    """Subtract one configured calendar or business-day country window."""

    days = int(policy["days"])
    window_type = str(policy["type"]).strip().lower()

    if window_type == "calendar_days":
        return max_date - pd.Timedelta(days=days)

    if window_type == "business_days":
        return max_date - BDay(days)

    raise RuntimeError(f"Unsupported dispute policy window type: {window_type}")


def _country_cutoffs(frame):
    """Calculate dynamic country MIN, MAX, and FAISS cutoff dates."""

    policy_config = get_dispute_policy_config()
    normalized_policy = {
        str(country).strip().casefold(): value
        for country, value in policy_config.items()
    }
    cutoffs = {}

    for country, country_frame in frame.groupby("country", sort=True):
        policy = normalized_policy.get(str(country).strip().casefold())

        if policy is None:
            raise RuntimeError(f"No dispute policy window configured for country: {country}")

        minimum_date = country_frame["creation_date"].min()
        maximum_date = country_frame["creation_date"].max()
        cutoff_date = _subtract_policy_window(maximum_date, policy)
        cutoffs[country] = {
            "minimum_date": minimum_date,
            "maximum_date": maximum_date,
            "cutoff_date": cutoff_date,
            "days": int(policy["days"]),
            "type": str(policy["type"]),
        }

    return cutoffs


def _split_temporally(frame, cutoffs):
    """Split complaints into historical index rows and recent held-out queries."""

    historical_parts = []
    held_out_parts = []

    for country, country_frame in frame.groupby("country", sort=True):
        cutoff = cutoffs[country]["cutoff_date"]
        historical_parts.append(
            country_frame[country_frame["creation_date"] < cutoff]
        )
        held_out_parts.append(
            country_frame[country_frame["creation_date"] >= cutoff]
        )

    historical_frame = pd.concat(historical_parts, ignore_index=True)
    held_out_frame = pd.concat(held_out_parts, ignore_index=True)

    if historical_frame.empty:
        raise RuntimeError("Temporal FAISS historical split contains no rows")

    if held_out_frame.empty:
        raise RuntimeError("Temporal FAISS held-out split contains no rows")

    return historical_frame, held_out_frame


def _safe_passages(descriptions):
    """Sanitize complaint descriptions and create E5 passage inputs."""

    passages = []

    for description in descriptions:
        language = detect_language(
            description,
            fallback=fallback_language,
        )
        safe_description = sanitize_text(
            description,
            language,
        )
        passages.append(f"passage: {safe_description}")

    return passages


def _evaluate_held_out(model, country_indexes, held_out_frame):
    """Return the simple held-out mean top-one similarity metric."""

    top_one_scores = []

    for country, country_frame in held_out_frame.groupby("country", sort=True):
        country_index = country_indexes.get(str(country).casefold())

        if country_index is None or country_index.ntotal <= 0:
            continue

        for start in range(0, len(country_frame), read_chunk_size):
            chunk = country_frame.iloc[start:start + read_chunk_size]
            queries = [
                passage.replace("passage: ", "query: ", 1)
                for passage in _safe_passages(
                    chunk["description"].astype(str).tolist()
                )
            ]
            vectors = model.encode(
                queries,
                batch_size=embedding_batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ).astype(np.float32)
            scores, indexes = country_index.search(vectors, 1)

            for score, index in zip(scores[:, 0], indexes[:, 0]):
                if index >= 0:
                    top_one_scores.append(float(score))

    return {
        "mean_top1_similarity": (
            float(np.mean(top_one_scores))
            if top_one_scores
            else None
        )
    }

def _serialize_cutoffs(cutoffs):
    """Convert timestamp cutoff metadata to JSON-friendly strings."""

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


def build_retrieval_index():
    """Build one country-aware historical FAISS complaint index from private RDS."""

    query = """
    SELECT
        c.complaint_id,
        c.description,
        c.creation_date,
        u.country
    FROM complaints c
    JOIN customers u
      ON u.customer_id = c.customer_id
    WHERE c.description IS NOT NULL
      AND BTRIM(c.description) <> ''
      AND c.creation_date IS NOT NULL
      AND u.country IS NOT NULL
    ORDER BY c.creation_date, c.complaint_id
    """
    frame = pd.read_sql(
        query,
        get_engine(),
    )

    if frame.empty:
        raise RuntimeError("No complaint descriptions were available to index")

    frame["creation_date"] = pd.to_datetime(
        frame["creation_date"],
        errors="coerce",
    )
    frame = frame.dropna(
        subset=[
            "complaint_id",
            "description",
            "creation_date",
            "country",
        ]
    ).reset_index(drop=True)

    if frame.empty:
        raise RuntimeError("No valid complaint rows remained after validation")

    cutoffs = _country_cutoffs(frame)
    historical_frame, held_out_frame = _split_temporally(frame, cutoffs)
    model = SentenceTransformer(model_name)
    index = None
    complaint_mapping = []
    country_indexes = {}

    for start in range(0, len(historical_frame), read_chunk_size):
        chunk = historical_frame.iloc[start:start + read_chunk_size]
        passages = _safe_passages(
            chunk["description"].astype(str).tolist()
        )
        vectors = model.encode(
            passages,
            batch_size=embedding_batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)

        if index is None:
            index = faiss.IndexFlatIP(vectors.shape[1])

        index.add(vectors)

        for row in chunk.itertuples(index=False):
            complaint_mapping.append(
                {
                    "complaint_id": str(row.complaint_id),
                    "country": str(row.country),
                }
            )

        chunk_countries = chunk["country"].astype(str).tolist()

        for country in sorted(set(chunk_countries)):
            positions = [
                index_position
                for index_position, value in enumerate(chunk_countries)
                if value == country
            ]

            if not positions:
                continue

            country_key = country.casefold()

            if country_key not in country_indexes:
                country_indexes[country_key] = faiss.IndexFlatIP(vectors.shape[1])

            country_indexes[country_key].add(
                vectors[np.asarray(positions, dtype=int)]
            )

    if index is None:
        raise RuntimeError("No historical complaint descriptions were available to index")

    evaluation = _evaluate_held_out(
        model=model,
        country_indexes=country_indexes,
        held_out_frame=held_out_frame,
    )
    asset_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    faiss.write_index(
        index,
        str(index_path),
    )
    mapping_path.write_text(
        json.dumps(
            complaint_mapping,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    published = publish_retrieval_assets()

    return {
        "index_path": str(index_path),
        "mapping_path": str(mapping_path),
        "complaints_indexed": len(complaint_mapping),
        "held_out_complaints": int(len(held_out_frame)),
        "country_cutoffs": _serialize_cutoffs(cutoffs),
        "held_out_evaluation": evaluation,
        **published,
    }


def main():
    """Build retrieval assets and print their locations."""

    print(build_retrieval_index())


if __name__ == "__main__":
    main()
