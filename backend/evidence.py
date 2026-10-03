import os
import uuid

import boto3
import fitz

from backend.database import (
    create_evidence_record,
    get_evidence_record,
    update_evidence_status,
)
from backend.privacy import sanitize_text


aws_region = os.getenv("AWS_REGION", "us-east-1")
evidence_bucket = os.getenv("EVIDENCE_BUCKET", "")
max_file_size = 10 * 1024 * 1024
max_extracted_characters = 40000
s3 = boto3.client(
    "s3",
    region_name=aws_region,
)


def create_pdf_upload(customer_id, content_type, file_size_bytes):
    """Create a customer-owned short-lived PDF upload form."""

    if content_type != "application/pdf":
        raise ValueError("Only PDF evidence is allowed")

    if file_size_bytes < 1 or file_size_bytes > max_file_size:
        raise ValueError("PDF must be between 1 byte and 10 MB")

    evidence_id = str(uuid.uuid4())
    object_key = f"evidence/raw/{evidence_id}.pdf"

    create_evidence_record(
        customer_id=customer_id,
        evidence_id=evidence_id,
        s3_key=object_key,
        content_type=content_type,
        file_size_bytes=file_size_bytes,
    )

    upload = s3.generate_presigned_post(
        Bucket=evidence_bucket,
        Key=object_key,
        Fields={"Content-Type": "application/pdf"},
        Conditions=[
            {"Content-Type": "application/pdf"},
            ["content-length-range", 1, max_file_size],
        ],
        ExpiresIn=300,
    )

    return {
        "evidence_id": evidence_id,
        "url": upload["url"],
        "fields": upload["fields"],
    }


def _extract_pdf_text(pdf_bytes):
    """Extract selectable text from a PDF."""

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )
    extracted = "\n".join(
        page.get_text("text")
        for page in document
    ).strip()
    document.close()

    if not extracted:
        raise ValueError("No selectable text found")

    return extracted[:max_extracted_characters]


def process_pdf_evidence(customer_id, evidence_id, language="en"):
    """Extract, sanitize, and store customer-owned evidence text."""

    record = get_evidence_record(
        customer_id=customer_id,
        evidence_id=evidence_id,
    )

    if record is None:
        raise LookupError("Evidence does not belong to the authenticated customer")

    response = s3.get_object(
        Bucket=evidence_bucket,
        Key=record["s3_key"],
    )
    file_size = response["ContentLength"]

    if file_size > max_file_size:
        raise ValueError("PDF is larger than the 10 MB limit")

    extracted_text = _extract_pdf_text(response["Body"].read())
    safe_text = sanitize_text(
        extracted_text,
        language,
    )
    processed_key = f"evidence/processed/{evidence_id}.txt"

    s3.put_object(
        Bucket=evidence_bucket,
        Key=processed_key,
        Body=safe_text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
        ServerSideEncryption="AES256",
    )

    update_evidence_status(
        customer_id=customer_id,
        evidence_id=evidence_id,
        processing_status="processed",
        file_size_bytes=file_size,
    )

    return {
        "evidence_id": evidence_id,
        "status": "processed",
        "characters": len(safe_text),
    }


def get_sanitized_evidence(customer_id, evidence_id):
    """Read sanitized evidence after customer ownership validation."""

    record = get_evidence_record(
        customer_id=customer_id,
        evidence_id=evidence_id,
    )

    if record is None:
        raise LookupError("Evidence does not belong to the authenticated customer")

    if record["processing_status"] != "processed":
        raise LookupError("Evidence has not been processed")

    response = s3.get_object(
        Bucket=evidence_bucket,
        Key=f"evidence/processed/{evidence_id}.txt",
    )
    return response["Body"].read().decode("utf-8")
