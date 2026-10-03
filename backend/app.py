import logging

from fastapi import Body, Depends, FastAPI, HTTPException, Query

from backend.auth import get_current_customer_id, get_optional_customer_id
from backend.database import (
    get_customer_transactions,
    get_dispute_case,
    get_historical_complaints,
    get_interaction_metrics,
    record_interaction_turn,
)
from backend.disputes import open_dispute
from backend.metrics import publish_resolution_metrics
from backend.openai_client import generate_reply
from backend.privacy import sanitize_text
from backend.secrets import get_prompt_config
from backend.worker_client import (
    predict_escalation_worker,
    read_sanitized_evidence,
    search_similar_cases_worker,
)


logger = logging.getLogger(__name__)
app = FastAPI(
    title="Factored AI Backend",
    docs_url=None,
    redoc_url=None,
)



@app.get("/health")
def health():
    """Return backend health status."""

    return {"status": "ok"}


@app.get("/messages/welcome")
def welcome_message(language=Query(default="en")):
    """Return the configured welcome message."""

    prompt_config = get_prompt_config()
    return {
        "message": prompt_config["WELCOME_MESSAGE"][language]
    }


@app.get("/transactions")
def transactions(customer_id=Depends(get_current_customer_id)):
    """Return recent transactions for the authenticated customer."""

    return {
        "transactions": get_customer_transactions(customer_id)
    }


@app.post("/disputes")
def create_dispute(payload=Body(...), customer_id=Depends(get_current_customer_id)):
    """Create a finalized dispute using Worker EC2 escalation inference."""

    transaction_id = payload.get("transaction_id", "").strip()
    reason = payload.get("reason", "").strip()
    language = payload.get("language", "en")
    interaction_id = payload.get("interaction_id", "").strip()

    if not interaction_id:
        raise HTTPException(
            status_code=400,
            detail="interaction_id is required",
        )

    if not transaction_id or not reason:
        raise HTTPException(
            status_code=400,
            detail="transaction_id and reason are required",
        )

    safe_reason = sanitize_text(
        reason,
        language,
    )

    try:
        prediction = predict_escalation_worker(safe_reason)
        dispute = open_dispute(
            customer_id=customer_id,
            transaction_id=transaction_id,
            reason=safe_reason,
            escalation_probability=prediction["escalation_probability"],
            requires_human_review=prediction["requires_human_review"],
        )
    except LookupError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=get_prompt_config()["FAILURE_MESSAGE"][language],
        ) from error

    successful_automated_resolution = dispute["status"] == "RESOLVED"

    try:
        final_metrics = get_interaction_metrics(interaction_id)

        if final_metrics is not None:
            final_metrics["successful_automated_resolution"] = successful_automated_resolution
            publish_resolution_metrics(final_metrics)
    except Exception:
        logger.exception("Interaction metric publication failed")

    response = None
    interaction_finished = False

    if dispute["status"] == "ESCALATED":
        response = get_prompt_config()["ESCALATION_MESSAGE"][language]
        interaction_finished = True

    return {
        "dispute": dispute,
        "response": response,
        "interaction_finished": interaction_finished,
    }


@app.get("/disputes/{dispute_id}")
def dispute_status(dispute_id, customer_id=Depends(get_current_customer_id)):
    """Return one dispute owned by the authenticated customer."""

    dispute = get_dispute_case(
        customer_id=customer_id,
        dispute_id=dispute_id,
    )

    if dispute is None:
        raise HTTPException(
            status_code=404,
            detail="Dispute not found",
        )

    return {"dispute": dispute}


@app.post("/chat")
def chat(payload=Body(...), customer_id=Depends(get_optional_customer_id)):
    """Generate an OpenAI response using sanitized worker-hosted context."""

    message = payload.get("message", "").strip()
    language = payload.get("language", "en")
    history = payload.get("history", [])
    evidence_ids = payload.get("evidence_ids", [])
    interaction_id = payload.get("interaction_id", "").strip()

    if not interaction_id:
        raise HTTPException(
            status_code=400,
            detail="interaction_id is required",
        )

    if not message:
        raise HTTPException(
            status_code=400,
            detail="message is required",
        )

    if evidence_ids and not customer_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication is required to use evidence",
        )

    safe_message = sanitize_text(
        message,
        language,
    )
    retrieval_texts = [safe_message]
    evidence_context = []

    try:
        for evidence_id in evidence_ids[:3]:
            safe_text = read_sanitized_evidence(
                evidence_id=evidence_id,
                customer_id=customer_id,
            )
            evidence_context.append(safe_text)
            retrieval_texts.append(safe_text)

        matches_by_id = {}

        for retrieval_text in retrieval_texts:
            for match in search_similar_cases_worker(
                retrieval_text,
                k=5,
            ):
                complaint_id = match["complaint_id"]
                previous = matches_by_id.get(complaint_id)

                if previous is None or match["score"] > previous["score"]:
                    matches_by_id[complaint_id] = match
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=get_prompt_config()["FAILURE_MESSAGE"][language],
        ) from error

    similar_matches = sorted(
        matches_by_id.values(),
        key=lambda item: item["score"],
        reverse=True,
    )[:5]
    complaint_rows = get_historical_complaints(
        [item["complaint_id"] for item in similar_matches]
    )
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

    reply = generate_reply(
        message=safe_message,
        language=language,
        history=history,
        evidence_context=evidence_context,
        similar_cases=similar_cases,
    )

    try:
        record_interaction_turn(
            interaction_id=interaction_id,
            total_tokens=reply["total_tokens"],
        )
    except Exception:
        logger.exception("Interaction metric persistence failed")

    return {
        "response": reply["response"]
    }
