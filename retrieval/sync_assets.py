import os
from pathlib import Path

import boto3


aws_region = os.getenv("AWS_REGION", "us-east-1")
runtime_asset_bucket = os.getenv("RUNTIME_ASSET_BUCKET", "").strip()
retrieval_asset_prefix = os.getenv(
    "RETRIEVAL_ASSET_PREFIX",
    "runtime-assets/retrieval",
).strip("/")
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


def download_asset(s3, key, destination):
    """Downloads one retrieval artifact atomically.

    Parameters
    ----------
    s3
        Configured boto3 S3 client.
    key : str
        Private S3 object key.
    destination : pathlib.Path
        Final local asset path.

    Returns
    -------
    pathlib.Path
        Downloaded local asset path.
    """
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    temporary_path = destination.with_suffix(
        destination.suffix + ".tmp"
    )

    s3.download_file(
        runtime_asset_bucket,
        key,
        str(temporary_path),
    )
    temporary_path.replace(destination)

    return destination


def sync_retrieval_assets():
    """Downloads the current FAISS artifacts for Retrieval EC2.

    Parameters
    ----------
    None.

    Returns
    -------
    dict
        Local paths synchronized from private S3.
    """
    if not runtime_asset_bucket:
        raise RuntimeError("RUNTIME_ASSET_BUCKET is not configured")

    s3 = boto3.client(
        "s3",
        region_name=aws_region,
    )
    index_key = f"{retrieval_asset_prefix}/complaints.faiss"
    mapping_key = f"{retrieval_asset_prefix}/complaint_ids.json"

    download_asset(
        s3,
        index_key,
        index_path,
    )
    download_asset(
        s3,
        mapping_key,
        mapping_path,
    )

    return {
        "index_path": str(index_path),
        "mapping_path": str(mapping_path),
    }


def main():
    """Synchronizes Retrieval EC2 runtime assets.

    Parameters
    ----------
    None.

    Returns
    -------
    None.
    """
    print(sync_retrieval_assets())


if __name__ == "__main__":
    main()
