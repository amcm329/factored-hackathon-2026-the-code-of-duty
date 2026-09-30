import os
import json
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
_complaint_ids = None


def _load_retrieval_assets():
    """Load E5, FAISS and the complaint ID mapping only when needed."""

    global _model, _index, _complaint_ids

    if _model is None:
        _model = SentenceTransformer(model_name)

    if _index is None and index_path.exists():
        _index = faiss.read_index(str(index_path))

    if _complaint_ids is None and mapping_path.exists():
        with mapping_path.open("r", encoding="utf-8") as file:
            _complaint_ids = json.load(file)


def search_similar_cases(text, k=5):
    """Return similar complaint IDs for sanitized evidence/message text."""

    _load_retrieval_assets()

    if _index is None or _complaint_ids is None:
        return []

    vector = _model.encode(
        [f"query: {text}"],
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    scores, indexes = _index.search(
        vector,
        k,
    )

    matches = []

    for score, index in zip(scores[0], indexes[0]):
        if index < 0 or index >= len(_complaint_ids):
            continue

        matches.append(
            {
                "complaint_id": _complaint_ids[index],
                "score": float(score),
            }
        )

    return matches
