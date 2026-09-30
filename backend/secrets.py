import os
import json
from functools import lru_cache

import boto3


secret_name = os.getenv(
    "OPENAI_SECRET_NAME",
    "factored/openai/api-key",
)

aws_region = os.getenv("AWS_REGION", "us-east-1")


@lru_cache(maxsize=1)
def get_openai_api_key():
    """Read the OpenAI API key from AWS Secrets Manager."""

    client = boto3.client(
        "secretsmanager",
        region_name=aws_region,
    )

    response = client.get_secret_value(
        SecretId=secret_name,
    )

    secret = json.loads(response["SecretString"])

    return secret["OPENAI_API_KEY"]
