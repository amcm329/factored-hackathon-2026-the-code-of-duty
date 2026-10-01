from fastapi import Body, FastAPI, HTTPException

from backend.database import get_historical_complaints
from backend.evidence import (
    create_pdf_upload,
    get_sanitized_evidence,
    process_pdf_evidence,
)
from backend.openai_client import generate_reply
from backend.privacy import sanitize_text
from backend.retrieval import search_similar_cases


app = FastAPI(
    title="Factored AI Backend",
    docs_url=None,
    redoc_url=None,
)


@app.get("/health")
def health():
    """Return backend health status.

    Returns:
        dict: Basic service status.
    """

    return {
        "status": "ok"
    }


@app.post("/evidence/presign")
def evidence_presign(payload=Body(...)):
    """Create a secure short-lived S3 upload form for one PDF.

    Parameters:
        payload: JSON request body containing the file content type.

    Returns:
        dict: Evidence ID and presigned S3 upload data.
    """

    content_type = payload.get("content_type", "")

    if content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF evidence is allowed.",
        )

    return create_pdf_upload()


@app.post("/evidence/process")
def evidence_process(payload=Body(...)):
    """Extract and sanitize one uploaded PDF.

    Parameters:
        payload: JSON request body containing evidence_id and language.

    Returns:
        dict: Evidence processing result.
    """

    evidence_id = payload.get("evidence_id", "").strip()
    language = payload.get("language", "en")

    if not evidence_id:
        raise HTTPException(
            status_code=400,
            detail="evidence_id is required",
        )

    try:
        return process_pdf_evidence(
            evidence_id=evidence_id,
            language=language,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@app.post("/chat")
def chat(payload=Body(...)):
    """Generate an OpenAI response with sanitized evidence and RDS history.

    Parameters:
        payload: JSON request body containing message, language, history, and evidence IDs.

    Returns:
        dict: Assistant response text.
    """

    message = payload.get("message", "").strip()
    language = payload.get("language", "en")
    history = payload.get("history", [])
    evidence_ids = payload.get("evidence_ids", [])

    if not message:
        raise HTTPException(
            status_code=400,
            detail="message is required",
        )

    evidence_context = []
    retrieval_texts = [
        sanitize_text(
            message,
            language,
        )
    ]

    for evidence_id in evidence_ids[:3]:
        safe_text = get_sanitized_evidence(evidence_id)
        evidence_context.append(safe_text)
        retrieval_texts.append(safe_text)

    matches_by_id = {}

    for retrieval_text in retrieval_texts:
        for match in search_similar_cases(
            retrieval_text,
            k=5,
        ):
            complaint_id = match["complaint_id"]
            previous = matches_by_id.get(complaint_id)

            if previous is None or match["score"] > previous["score"]:
                matches_by_id[complaint_id] = match

    similar_matches = sorted(
        matches_by_id.values(),
        key=lambda item: item["score"],
        reverse=True,
    )[:5]

    complaint_ids = [
        match["complaint_id"]
        for match in similar_matches
    ]

    complaint_rows = get_historical_complaints(complaint_ids)
    complaints_by_id = {
        row["complaint_id"]: row
        for row in complaint_rows
    }

    similar_cases = []

    for match in similar_matches:
        row = complaints_by_id.get(match["complaint_id"])

        if row is None:
            continue

        similar_cases.append(
            {
                "score": match["score"],
                "category": row.get("category") or "",
                "subcategory": row.get("subcategory") or "",
                "priority": row.get("priority") or "",
                "status": row.get("status") or "",
                "description": sanitize_text(
                    row.get("description") or "",
                    language,
                )[:1500],
                "resolution": sanitize_text(
                    row.get("resolution") or "",
                    language,
                )[:1500],
            }
        )

    response = generate_reply(
        message=message,
        language=language,
        history=history,
        evidence_context=evidence_context,
        similar_cases=similar_cases,
    )

    return {
        "response": response
    }