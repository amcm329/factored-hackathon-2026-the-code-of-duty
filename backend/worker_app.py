from fastapi import Body, Depends, FastAPI, HTTPException

from backend.auth import get_current_customer_id
from backend.escalation import predict_escalation
from backend.evidence import (
    create_pdf_upload,
    get_sanitized_evidence,
    process_pdf_evidence,
)
from backend.retrieval import search_similar_cases


app = FastAPI(
    title="Factored AI Worker",
    docs_url=None,
    redoc_url=None,
)


@app.get("/health")
def health():
    """Return worker health status."""

    return {"status": "ok"}


@app.post("/evidence/presign")
def evidence_presign(payload=Body(...), customer_id=Depends(get_current_customer_id)):
    """Create a private PDF upload for the authenticated customer."""

    try:
        return create_pdf_upload(
            customer_id=customer_id,
            content_type=payload.get("content_type", ""),
            file_size_bytes=int(payload.get("size", 0)),
        )
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@app.post("/evidence/process")
def evidence_process(payload=Body(...), customer_id=Depends(get_current_customer_id)):
    """Process one customer-owned PDF."""

    evidence_id = payload.get("evidence_id", "").strip()
    language = payload.get("language", "en")

    if not evidence_id:
        raise HTTPException(
            status_code=400,
            detail="evidence_id is required",
        )

    try:
        return process_pdf_evidence(
            customer_id=customer_id,
            evidence_id=evidence_id,
            language=language,
        )
    except (LookupError, ValueError) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@app.post("/internal/evidence/read")
def internal_evidence_read(payload=Body(...)):
    """Return sanitized customer-owned evidence to Chat EC2."""

    try:
        return {
            "text": get_sanitized_evidence(
                customer_id=payload.get("customer_id", ""),
                evidence_id=payload.get("evidence_id", ""),
            )
        }
    except LookupError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@app.post("/internal/retrieval/search")
def internal_retrieval_search(payload=Body(...)):
    """Run E5 and FAISS similarity search."""

    text = payload.get("text", "").strip()
    k = min(max(int(payload.get("k", 5)), 1), 20)

    if not text:
        raise HTTPException(
            status_code=400,
            detail="text is required",
        )

    return {
        "matches": search_similar_cases(
            text=text,
            k=k,
        )
    }


@app.post("/internal/escalation/predict")
def internal_escalation_predict(payload=Body(...)):
    """Run VAD extraction and Logistic Regression inference."""

    text = payload.get("text", "").strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail="text is required",
        )

    try:
        return predict_escalation(text)
    except (RuntimeError, ValueError) as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
