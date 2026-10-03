import json
import os
from pathlib import Path
import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from backend.database import get_engine

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


def build_retrieval_index():
    """Build the FAISS complaint index from the private RDS complaints table.

    Parameters
    ----------
    None.

    Returns
    -------
    dict
        Paths and number of complaint vectors written.
    """
    model = SentenceTransformer(model_name)
    index = None
    complaint_ids = []

    query = """
    SELECT complaint_id, description
    FROM complaints
    WHERE description IS NOT NULL
    AND BTRIM(description) <> ''
    ORDER BY complaint_id
    """

    for chunk in pd.read_sql(
        query,
        get_engine(),
        chunksize=read_chunk_size,
    ):
        passages = [
            f"passage: {description}"
            for description in chunk["description"].astype(str).tolist()
        ]

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

        complaint_ids.extend(
            chunk["complaint_id"].astype(str).tolist()
        )

    if index is None:
        raise RuntimeError("No complaint descriptions were available to index.")

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
            complaint_ids,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return {
        "index_path": str(index_path),
        "mapping_path": str(mapping_path),
        "complaints_indexed": len(complaint_ids),
    }


def main():
    """Build retrieval assets and print their locations.

    Parameters
    ----------
    None.

    Returns
    -------
    None.
    """
    print(build_retrieval_index())


if __name__ == "__main__":
    main()
