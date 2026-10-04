import json
import os
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


model_name = os.getenv(
    "E5_MODEL",
    "intfloat/multilingual-e5-base",
)

index_path = Path(
    os.getenv(
        "FAISS_INDEX_PATH",
        "/opt/factored-ai/retrieval_assets/complaints.faiss",
    )
)

mapping_path = Path(
    os.getenv(
        "FAISS_MAPPING_PATH",
        "/opt/factored-ai/retrieval_assets/complaint_ids.json",
    )
)

_model = None
_index = None
_complaint_mapping = None


def _load_retrieval_assets():
    """Load E5, FAISS, and complaint metadata when first needed.

    Returns:
        None
    """

    global _model, _index, _complaint_mapping

    if _model is None:
        _model = SentenceTransformer(model_name)

    if _index is None and index_path.exists():
        _index = faiss.read_index(str(index_path))

    if _complaint_mapping is None and mapping_path.exists():
        with mapping_path.open("r", encoding="utf-8") as file:
            _complaint_mapping = json.load(file)

    if _index is not None and _complaint_mapping is not None:
        if _index.ntotal != len(_complaint_mapping):
            raise RuntimeError(
                "FAISS index and complaint mapping contain different row counts."
            )


def search_similar_cases(text, country, k=5):
    """Return the nearest historical complaints from the requested country.

    Parameters:
        text: Sanitized current complaint or evidence text.
        country: Authenticated customer country.
        k: Maximum number of nearest complaints to return.

    Returns:
        list: Complaint IDs and similarity scores from the internal FAISS index.
    """

    _load_retrieval_assets()

    if _index is None or _complaint_mapping is None:
        return []

    if not country:
        return []

    vector = _model.encode(
        [f"query: {text}"],
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    requested_country = country.strip().casefold()
    result_count = min(
        max(k * 10, 50),
        _index.ntotal,
    )

    while result_count > 0:
        scores, indexes = _index.search(
            vector,
            result_count,
        )
        matches = []

        for score, index in zip(scores[0], indexes[0]):
            if index < 0 or index >= len(_complaint_mapping):
                continue

            metadata = _complaint_mapping[index]

            if not isinstance(metadata, dict):
                raise RuntimeError(
                    "FAISS complaint mapping is missing country metadata."
                )

            if str(metadata.get("country", "")).strip().casefold() != requested_country:
                continue

            matches.append(
                {
                    "complaint_id": str(metadata["complaint_id"]),
                    "score": float(score),
                }
            )

            if len(matches) >= k:
                return matches

        if result_count >= _index.ntotal:
            return matches

        result_count = min(
            result_count * 2,
            _index.ntotal,
        )

    return []
