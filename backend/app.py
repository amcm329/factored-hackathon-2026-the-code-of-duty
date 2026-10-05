import logging

from fastapi import Body, Depends, FastAPI, HTTPException, Query

from backend.auth import (
    get_current_customer_context,
    get_current_customer_id,
    get_optional_customer_context,
)
from backend.database import (
    create_dispute_case,
    finalize_interaction_metrics,
    get_customer_case_history,
    get_customer_segment,
    get_customer_transactions,
    get_historical_complaints,
    record_interaction_turn,
    start_interaction_metrics,
)
from backend.language import detect_language
from backend.metrics import publish_resolution_metrics
from backend.openai_client import generate_reply
from backend.privacy import sanitize_text
from backend.retrieval_client import search_similar_cases_retrieval
from backend.secrets import get_prompt_config
from backend.worker_client import predict_escalation_worker


logger = logging.getLogger(__name__)
app = FastAPI(
    title="Factored AI Backend",
    docs_url=None,
    redoc_url=None,
)

supported_languages = {"en", "es", "pt"}
personal_dispute_signals = (
    "i don't recognize",
    "i do not recognize",
    "i want to dispute",
    "i need to dispute",
    "not my transaction",
    "not my purchase",
    "unauthorized transaction",
    "unauthorised transaction",
    "unauthorized charge",
    "unauthorised charge",
    "my card was charged",
    "charged my card",
    "dispute this transaction",
    "open a dispute",
    "this transaction isn't mine",
    "this transaction is not mine",
    "no reconozco",
    "quiero disputar",
    "necesito disputar",
    "no es mi transacción",
    "no es mi transaccion",
    "no es mi compra",
    "cargo no reconocido",
    "transacción no reconocida",
    "transaccion no reconocida",
    "compra no reconocida",
    "cargaron mi tarjeta",
    "me cobraron",
    "disputar esta transacción",
    "disputar esta transaccion",
    "abrir una disputa",
    "desconozco este cargo",
    "desconozco esta transacción",
    "desconozco esta transaccion",
    "este cargo no es mío",
    "este cargo no es mio",
    "quiero reportar este cargo",
    "quiero escalar con un humano",
    "quiero hablar con un humano",
    "quiero hablar con una persona",
    "quiero un representante",
    "não reconheço",
    "quero contestar",
    "preciso contestar",
    "nao reconheco",
    "não é minha transação",
    "nao e minha transacao",
    "transação não reconhecida",
    "transacao nao reconhecida",
    "compra não reconhecida",
    "compra nao reconhecida",
    "me cobraram",
    "cobraram meu cartão",
    "cobraram meu cartao",
    "contestar esta transação",
    "contestar esta transacao",
    "abrir uma contestação",
    "abrir uma contestacao",
)


case_history_signals = (
    "mis disputas",
    "mis casos",
    "mis reclamos",
    "historial de disputas",
    "historial de reclamos",
    "muéstrame mis disputas",
    "muestrame mis disputas",
    "quiero ver mis disputas",
    "quiero ver mis casos",
    "my disputes",
    "my cases",
    "my complaints",
    "minhas contestações",
    "minhas contestacoes",
    "minhas reclamações",
    "minhas reclamacoes",
)


def _normalize_for_intent(value):
    return " ".join(str(value or "").lower().replace("’", "'").split())


def _is_case_history_request(message):
    """Detect requests for the authenticated customer's own case history."""
    normalized = _normalize_for_intent(message)
    return any(signal in normalized for signal in case_history_signals)


def _format_case_history_response(cases, language):
    """Format private RDS case history without sending it to OpenAI."""
    if not cases:
        return {
            "en": "I found no disputes or complaints associated with your account.",
            "es": "No encontré disputas ni reclamos asociados con tu cuenta.",
            "pt": "Não encontrei contestações ou reclamações associadas à sua conta.",
        }[language]

    headings = {
        "en": "These are your most recent disputes and complaints:",
        "es": "Estas son tus disputas y reclamos más recientes:",
        "pt": "Estas são suas contestações e reclamações mais recentes:",
    }
    lines = [headings[language]]

    for index, case in enumerate(cases[:10], start=1):
        case_date = case.get("case_date")
        date_text = (
            case_date.strftime("%Y-%m-%d")
            if hasattr(case_date, "strftime")
            else str(case_date or "")[:10]
        )
        amount = case.get("claimed_amount")
        currency = str(case.get("currency") or "").strip()
        amount_text = f"{currency} {amount}".strip() if amount is not None else "-"
        label = case.get("category") or case.get("case_type") or "-"
        lines.append(
            f"{index}. {case['case_id']} | {date_text} | "
            f"{case.get('status') or '-'} | {label} | {amount_text}"
        )

    return "\n".join(lines)


def _normalize_language(language):
    """Return a supported response language code."""

    normalized = str(language or "").strip().lower()
    return normalized if normalized in supported_languages else "en"


def _is_personal_dispute_message(message):
    """Detect simple personal transaction-dispute intent without another model."""

    normalized = _normalize_for_intent(message)
    return any(signal in normalized for signal in personal_dispute_signals)


@app.get("/health")
def health():
    """Return backend health status."""

    return {"status": "ok"}


@app.get("/messages/welcome")
def welcome_message(language=Query(default="en")):
    """Return the configured welcome message."""

    language = _normalize_language(language)
    prompt_config = get_prompt_config()
    return {
        "message": prompt_config["WELCOME_MESSAGE"][language]
    }


@app.get("/transactions")
def transactions(customer_id=Depends(get_current_customer_id)):
    """Return recent transactions for explicit customer selection."""

    return {
        "transactions": get_customer_transactions(customer_id)
    }


@app.post("/disputes")
def create_dispute(payload=Body(...), customer_context=Depends(get_current_customer_context)):
    """Create one dispute after explicit transaction selection and model inference."""

    customer_id = customer_context["customer_id"]
    country = customer_context["country"]
    transaction_id = payload.get("transaction_id", "").strip()
    reason = payload.get("reason", "").strip()
    language = _normalize_language(payload.get("language", "en"))
    interaction_id = payload.get("interaction_id", "").strip()
    evidence_ids = payload.get("evidence_ids", []) or []

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

    if not isinstance(evidence_ids, list) or len(evidence_ids) > 3:
        raise HTTPException(
            status_code=400,
            detail="evidence_ids must contain at most three items",
        )

    reason_language = detect_language(
        reason,
        fallback=language,
    )
    safe_reason = sanitize_text(
        reason,
        reason_language,
    )

    try:
        segment = get_customer_segment(customer_id)
        prediction = predict_escalation_worker(
            text=safe_reason,
            language=reason_language,
            country=country,
            segment=segment,
        )
        dispute = create_dispute_case(
            customer_id=customer_id,
            transaction_id=transaction_id,
            reason=safe_reason,
            escalation_probability=prediction["escalation_probability"],
            requires_human_review=prediction["requires_human_review"],
            evidence_ids=evidence_ids,
        )
    except LookupError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=get_prompt_config()["FAILURE_MESSAGE"][language],
        ) from error

    try:
        final_metrics = finalize_interaction_metrics(
            interaction_id=interaction_id,
            successful_automated_resolution=False,
        )
        publish_resolution_metrics(final_metrics)
    except Exception:
        logger.exception("Interaction metric publication failed")

    response = None

    if dispute["status"] == "ESCALATED":
        response = get_prompt_config()["ESCALATION_MESSAGE"][language]

    return {
        "dispute": dispute,
        "response": response,
        "interaction_finished": True,
    }


@app.post("/chat")
def chat(payload=Body(...), customer_context=Depends(get_optional_customer_context)):
    """Generate chat responses and deterministic satisfaction feedback handling."""

    customer_id = customer_context["customer_id"] if customer_context else None
    country = customer_context["country"] if customer_context else None
    language = _normalize_language(payload.get("language", "en"))
    interaction_id = payload.get("interaction_id", "").strip()
    feedback = str(payload.get("feedback", "")).strip().lower()

    if not interaction_id:
        raise HTTPException(
            status_code=400,
            detail="interaction_id is required",
        )

    if feedback:
        if feedback not in {"yes", "no"}:
            raise HTTPException(
                status_code=400,
                detail="feedback must be yes or no",
            )

        if not customer_id:
            raise HTTPException(
                status_code=401,
                detail="Authentication is required to submit dispute feedback",
            )

        if feedback == "yes":
            try:
                final_metrics = finalize_interaction_metrics(
                    interaction_id=interaction_id,
                    successful_automated_resolution=True,
                )
                publish_resolution_metrics(final_metrics)
            except Exception:
                logger.exception("Interaction metric publication failed")

            return {
                "response": None,
                "interaction_finished": True,
                "needs_transaction_selection": False,
                "successful_automated_resolution": True,
            }

        return {
            "response": None,
            "interaction_finished": False,
            "needs_transaction_selection": True,
            "successful_automated_resolution": False,
        }

    message = payload.get("message", "").strip()
    history = payload.get("history", [])

    if not message:
        raise HTTPException(
            status_code=400,
            detail="message is required",
        )

    if _is_case_history_request(message):
        if not customer_id:
            return {
                "response": None,
                "authentication_required": True,
                "personal_dispute": False,
                "needs_satisfaction_feedback": False,
                "needs_transaction_selection": False,
            }

        try:
            cases = get_customer_case_history(customer_id=customer_id, limit=20)
        except Exception as error:
            logger.exception("Customer case-history lookup failed")
            raise HTTPException(
                status_code=502,
                detail=get_prompt_config()["FAILURE_MESSAGE"][language],
            ) from error

        return {
            "response": _format_case_history_response(cases, language),
            "personal_dispute": False,
            "retrieval_used": False,
            "needs_satisfaction_feedback": False,
            "needs_transaction_selection": False,
            "authentication_required": False,
        }

    try:
        start_interaction_metrics(interaction_id)
    except Exception:
        logger.exception("Interaction metric start failed")

    personal_dispute = _is_personal_dispute_message(message)

    if personal_dispute and not customer_id:
        return {
            "response": None,
            "authentication_required": True,
            "personal_dispute": True,
            "needs_satisfaction_feedback": False,
            "needs_transaction_selection": False,
        }

    message_language = detect_language(
        message,
        fallback=language,
    )
    safe_message = sanitize_text(
        message,
        message_language,
    )
    evidence_context = []
    similar_matches = []

    if personal_dispute and country:
        matches_by_id = {}

        try:
            for match in search_similar_cases_retrieval(
                text=safe_message,
                country=country,
                k=5,
            ):
                complaint_id = match["complaint_id"]
                previous = matches_by_id.get(complaint_id)

                if previous is None or match["score"] > previous["score"]:
                    matches_by_id[complaint_id] = match
        except Exception:
            logger.exception(
                "Retrieval request failed; continuing without historical matches"
            )
            matches_by_id = {}

        similar_matches = sorted(
            matches_by_id.values(),
            key=lambda item: item["score"],
            reverse=True,
        )[:5]

    try:
        complaint_rows = (
            get_historical_complaints(
                [item["complaint_id"] for item in similar_matches],
                country,
            )
            if country and similar_matches
            else []
        )
    except Exception:
        logger.exception(
            "Historical complaint lookup failed; continuing without historical matches"
        )
        similar_matches = []
        complaint_rows = []
    complaints_by_id = {
        row["complaint_id"]: row
        for row in complaint_rows
    }
    similar_cases = []

    for match in similar_matches:
        row = complaints_by_id.get(match["complaint_id"])

        if row is None:
            continue

        description = row.get("description") or ""
        resolution = row.get("resolution") or ""
        description_language = detect_language(
            description,
            fallback=language,
        )
        resolution_language = detect_language(
            resolution,
            fallback=description_language,
        )

        similar_cases.append(
            {
                "score": match["score"],
                "category": row.get("category") or "",
                "subcategory": row.get("subcategory") or "",
                "priority": row.get("priority") or "",
                "status": row.get("status") or "",
                "description": sanitize_text(
                    description,
                    description_language,
                )[:1500],
                "resolution": sanitize_text(
                    resolution,
                    resolution_language,
                )[:1500],
            }
        )

    if personal_dispute and customer_id and not similar_cases:
        return {
            "response": None,
            "personal_dispute": True,
            "needs_satisfaction_feedback": False,
            "needs_transaction_selection": True,
            "retrieval_used": False,
        }

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

    retrieval_used = bool(similar_cases)
    return {
        "response": reply["response"],
        "personal_dispute": personal_dispute,
        "retrieval_used": retrieval_used,
        "needs_satisfaction_feedback": bool(
            personal_dispute and customer_id and retrieval_used
        ),
        "needs_transaction_selection": False,
        "authentication_required": False,
    }
