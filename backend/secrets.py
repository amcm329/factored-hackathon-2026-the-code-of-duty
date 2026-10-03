import json
import os
from functools import lru_cache

import boto3


aws_region = os.getenv("AWS_REGION", "us-east-1")
openai_secret_name = os.getenv(
    "OPENAI_SECRET_NAME",
    "factored/openai/api-key",
)
organizer_s3_secret_name = os.getenv(
    "ORGANIZER_S3_SECRET_NAME",
    "factored/organizer-s3/read-only",
)
database_secret_name = os.getenv(
    "DATABASE_SECRET_NAME",
    "factored/database/url",
)
prompts_secret_name = "factored/prompts"


@lru_cache(maxsize=8)
def _get_json_secret(secret_name):
    """Read one JSON secret from AWS Secrets Manager."""

    client = boto3.client(
        "secretsmanager",
        region_name=aws_region,
    )
    response = client.get_secret_value(
        SecretId=secret_name,
    )
    return json.loads(response["SecretString"])


def get_openai_api_key():
    """Return the OpenAI API key."""

    return _get_json_secret(openai_secret_name)["OPENAI_API_KEY"]


def get_organizer_s3_config():
    """Return read-only organizer S3 connection values."""

    return _get_json_secret(organizer_s3_secret_name)


def get_database_url():
    """Return the private PostgreSQL/RDS connection URL."""

    return _get_json_secret(database_secret_name)["DATABASE_URL"]


def get_prompt_config():
    """Return prompt and fixed-message configuration."""

    return _get_json_secret(prompts_secret_name)
