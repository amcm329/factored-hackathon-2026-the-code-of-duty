import os
import uuid

import fitz
import boto3

from backend.privacy import sanitize_text


aws_region = os.getenv("AWS_REGION", "us-east-1")
evidence_bucket = os.getenv("EVIDENCE_BUCKET", "")
max_file_size = 10 * 1024 * 1024
max_extracted_characters = 40000

s3 = boto3.client(
    "s3",
    region_name=aws_region,
)


def create_pdf_upload():
    """Create a short-lived presigned POST for one private PDF upload."""

    evidence_id = str(uuid.uuid4())
    object_key = f"evidence/raw/{evidence_id}.pdf"

    upload = s3.generate_presigned_post(
        Bucket=evidence_bucket,
        Key=object_key,
        Fields={
            "Content-Type": "application/pdf",
        },
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

    text = "
".join(
        page.get_text("text")
        for page in document
    ).strip()

    if not text:
        raise ValueError(
            "No selectable text found. A scanned PDF requires OCR/Textract."
        )

    return text[:max_extracted_characters]


def process_pdf_evidence(evidence_id, language="en"):
    """Read a private PDF, extract text, sanitize it and store safe text."""

    raw_key = f"evidence/raw/{evidence_id}.pdf"
    processed_key = f"evidence/processed/{evidence_id}.txt"

    response = s3.get_object(
        Bucket=evidence_bucket,
        Key=raw_key,
    )

    file_size = response["ContentLength"]

    if file_size > max_file_size:
        raise ValueError("PDF is larger than the 10 MB limit.")

    pdf_bytes = response["Body"].read()
    extracted_text = _extract_pdf_text(pdf_bytes)
    safe_text = sanitize_text(
        extracted_text,
        language,
    )

    s3.put_object(
        Bucket=evidence_bucket,
        Key=processed_key,
        Body=safe_text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
        ServerSideEncryption="AES256",
    )

    return {
        "evidence_id": evidence_id,
        "status": "processed",
        "characters": len(safe_text),
    }


def get_sanitized_evidence(evidence_id):
    """Read previously sanitized evidence text from the private S3 bucket."""

    processed_key = f"evidence/processed/{evidence_id}.txt"

    response = s3.get_object(
        Bucket=evidence_bucket,
        Key=processed_key,
    )

    return response["Body"].read().decode("utf-8")