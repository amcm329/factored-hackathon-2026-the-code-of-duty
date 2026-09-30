from fastapi import Body, FastAPI, HTTPException

from backend.evidence import (
    create_pdf_upload,
    get_sanitized_evidence,
    process_pdf_evidence,
)
from backend.openai_client import generate_reply
from backend.retrieval import search_similar_cases


app = FastAPI(
    title="Factored AI Backend",
    docs_url=None,
    redoc_url=None,
)


@app.get("/health")
def health():
    """Return backend health status."""

    return {
        "status": "ok"
    }


@app.post("/evidence/presign")
def evidence_presign(payload=Body(...)):
    """Create a secure short-lived S3 upload form for one PDF."""

    content_type = payload.get("content_type", "")

    if content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF evidence is allowed.",
        )

    return create_pdf_upload()


@app.post("/evidence/process")
def evidence_process(payload=Body(...)):
    """Extract and sanitize one uploaded PDF."""

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
    """Generate an OpenAI-backed response with optional sanitized PDF evidence."""

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
    similar_cases = []

    for evidence_id in evidence_ids[:3]:
        safe_text = get_sanitized_evidence(evidence_id)
        evidence_context.append(safe_text)
        similar_cases.extend(
            search_similar_cases(
                safe_text,
                k=3,
            )
        )

    response = generate_reply(
        message=message,
        language=language,
        history=history,
        evidence_context=evidence_context,
        similar_cases=similar_cases[:5],
    )

    return {
        "response": response
    }