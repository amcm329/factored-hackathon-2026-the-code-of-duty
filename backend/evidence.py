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
    """Create a short-lived presigned POST for one private PDF upload.

    Returns:
        dict: Evidence ID, S3 upload URL, and required form fields.
    """

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
    """Extract selectable text from a PDF.

    Parameters:
        pdf_bytes: Raw PDF bytes read from the private S3 object.

    Returns:
        str: Extracted text limited to the configured character maximum.
    """

    document = fitz.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    text = "\n".join(
        page.get_text("text")
        for page in document
    ).strip()

    if not text:
        raise ValueError(
            "No selectable text found. A scanned PDF requires OCR/Textract."
        )

    return text[:max_extracted_characters]


def process_pdf_evidence(evidence_id, language="en"):
    """Read a private PDF, sanitize its text, and store only safe text.

    Parameters:
        evidence_id: Generated evidence identifier used in the private S3 key.
        language: Presidio language code: en, es, or pt.

    Returns:
        dict: Evidence ID, processing status, and sanitized character count.
    """

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
    """Read sanitized evidence text from the private S3 bucket.

    Parameters:
        evidence_id: Generated evidence identifier.

    Returns:
        str: Previously sanitized evidence text.
    """

    processed_key = f"evidence/processed/{evidence_id}.txt"

    response = s3.get_object(
        Bucket=evidence_bucket,
        Key=processed_key,
    )