import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError


logger = logging.getLogger(__name__)
aws_region = os.getenv("AWS_REGION", "us-east-1")
metric_namespace = os.getenv("CLOUDWATCH_METRIC_NAMESPACE", "FactoredAI/Disputes")
cloudwatch = boto3.client(
    "cloudwatch",
    region_name=aws_region,
)


def publish_resolution_metrics(metrics):
    """Publish the four selected workflow metrics to CloudWatch."""

    successful = bool(metrics["successful_automated_resolution"])
    metric_data = [
        {
            "MetricName": "SuccessfulAutomatedResolutionRate",
            "Value": 100.0 if successful else 0.0,
            "Unit": "Percent",
        },
        {
            "MetricName": "EndToEndLatency",
            "Value": float(metrics["end_to_end_latency_ms"]),
            "Unit": "Milliseconds",
        },
    ]

    if successful:
        metric_data.extend(
            [
                {
                    "MetricName": "TurnsToResolution",
                    "Value": float(metrics["turn_count"]),
                    "Unit": "Count",
                },
                {
                    "MetricName": "TokensPerSuccessfulAutomatedResolution",
                    "Value": float(metrics["total_tokens"]),
                    "Unit": "Count",
                },
            ]
        )

    try:
        cloudwatch.put_metric_data(
            Namespace=metric_namespace,
            MetricData=metric_data,
        )
    except (BotoCoreError, ClientError):
        logger.exception("CloudWatch metric publication failed")


def publish_escalation_recall(recall_value):
    """Publish held-out escalation recall to CloudWatch."""

    try:
        cloudwatch.put_metric_data(
            Namespace=metric_namespace,
            MetricData=[
                {
                    "MetricName": "EscalationRecall",
                    "Value": float(recall_value),
                    "Unit": "None",
                }
            ],
        )
    except (BotoCoreError, ClientError):
        logger.exception("Escalation recall publication failed")
