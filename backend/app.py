import logging
import os
import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import Body, Depends, FastAPI, HTTPException, Query

from backend.auth import (
    get_current_customer_context,
    get_optional_customer_context,
)
from backend.database import (
    create_dispute_case,
    finalize_interaction_metrics,
    get_customer_case,
    get_customer_case_history,
    get_customer_segment,
    get_customer_transaction,
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
from backend.secrets import get_dispute_policy_config, get_prompt_config
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

transaction_history_signals = (
    "mis transacciones",
    "mis movimientos",
    "ver mis transacciones",
    "quiero ver mis transacciones",
    "historial de transacciones",
    "transacciones desde",
    "my transactions",
    "transaction history",
    "transactions from",
    "minhas transações",
    "minhas transacoes",
    "histórico de transações",
    "historico de transacoes",
    "transações desde",
    "transacoes desde",
)

human_escalation_signals = (
    "talk to a human",
    "speak to a human",
    "talk to an agent",
    "speak to an agent",
    "human agent",
    "representative",
    "escalate to a human",
    "quiero un humano",
    "hablar con un humano",
    "hablar con un agente",
    "hablar con una persona",
    "quiero un representante",
    "escalar con un humano",
    "escalar a un humano",
    "mándame con",
    "mandame con",
    "falar com um humano",
    "falar com um agente",
    "representante humano",
)


ambiguous_transaction_signals = (
    "i have a problem with a transaction",
    "i have an issue with a transaction",
    "there is a problem with a transaction",
    "transaction problem",
    "transaction issue",
    "tengo un problema con una transacción",
    "tengo un problema con una transaccion",
    "tengo un problema con un cargo",
    "problema con una transacción",
    "problema con una transaccion",
    "problema con un cargo",
    "tenho um problema com uma transação",
    "tenho um problema com uma transacao",
    "problema com uma transação",
    "problema com uma transacao",
)



out_of_scope_banking_signals = (
    "withdraw money",
    "cash withdrawal",
    "withdraw cash",
    "make a transfer",
    "transfer money",
    "send money",
    "loan application",
    "apply for a loan",
    "open an account",
    "close my account",
    "retirar dinero",
    "retirar mi dinero",
    "quiero retirar",
    "sacar dinero",
    "sacar mi dinero",
    "sacar tu dinero",
    "quiero sacar",
    "retiro en efectivo",
    "hacer una transferencia",
    "transferir dinero",
    "enviar dinero",
    "solicitar un préstamo",
    "solicitar un prestamo",
    "abrir una cuenta",
    "cerrar mi cuenta",
    "sacar efectivo",
    "sacar plata",
    "retirar efectivo",
    "sacar do caixa",
    "retirar dinheiro",
    "retirar meu dinheiro",
    "quero retirar",
    "saque em dinheiro",
    "quero sacar",
    "fazer uma transferência",
    "fazer uma transferencia",
    "transferir dinheiro",
    "enviar dinheiro",
    "solicitar empréstimo",
    "solicitar emprestimo",
    "abrir uma conta",
    "fechar minha conta",
)


dispute_scope_terms = (
    "dispute",
    "disputed",
    "complaint",
    "unrecognized",
    "unauthorized",
    "transaction",
    "charge",
    "disputa",
    "reclamo",
    "reclamación",
    "reclamacion",
    "no reconozco",
    "cargo",
    "transacción",
    "transaccion",
    "contestação",
    "contestacao",
    "reclamação",
    "reclamacao",
    "não reconheço",
    "nao reconheco",
    "transação",
    "transacao",
)



def _normalize_country_key(value):
    normalized = unicodedata.normalize("NFKD", str(value or "").strip())
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).casefold()


_COUNTRY_TIMEZONES = {
    "mexico": "America/Mexico_City",
    "colombia": "America/Bogota",
    "argentina": "America/Argentina/Buenos_Aires",
    "brazil": "America/Sao_Paulo",
    "brasil": "America/Sao_Paulo",
}


def _country_local_now(country):
    """Return the current local date/time for the authenticated customer's country."""

    timezone_name = _COUNTRY_TIMEZONES.get(_normalize_country_key(country), "UTC")
    return datetime.now(ZoneInfo(timezone_name))


def _dispute_reference_date(country):
    """Return the configured dispute reference date or the current local date."""

    demo_mode = os.getenv("DEMO_MODE", "0").strip() == "1"
    demo_reference_date = os.getenv("DEMO_REFERENCE_DATE", "").strip()

    if demo_mode:
        if not demo_reference_date:
            raise RuntimeError("DEMO_REFERENCE_DATE is required when DEMO_MODE=1")
        return date.fromisoformat(demo_reference_date)

    return _country_local_now(country).date()


def _country_policy(country):
    """Return the configured dispute-window policy for a customer's country."""

    policy_config = get_dispute_policy_config()
    normalized_policy = {
        _normalize_country_key(name): value
        for name, value in policy_config.items()
    }
    policy = normalized_policy.get(_normalize_country_key(country))
    if policy is None:
        raise RuntimeError(f"No dispute policy configured for country: {country}")

    return {
        "days": int(policy["days"]),
        "type": str(policy["type"]).strip().lower(),
    }


def _subtract_business_days(reference_date, days):
    current = reference_date
    remaining = int(days)
    while remaining > 0:
        current -= timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _country_policy_cutoff(country, reference_date=None):
    """Return the earliest currently disputable date using the configured country policy."""

    reference_date = reference_date or _dispute_reference_date(country)
    policy = _country_policy(country)
    days = policy["days"]
    window_type = policy["type"]
    if window_type == "calendar_days":
        return reference_date - timedelta(days=days)
    if window_type == "business_days":
        return _subtract_business_days(reference_date, days)
    raise RuntimeError(f"Unsupported dispute policy window type: {window_type}")


def _transaction_date_value(transaction):
    value = (transaction or {}).get("transaction_date")
    if value is None:
        return None
    if isinstance(value, date):
        return value if type(value) is date else value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _transaction_is_currently_disputable(transaction, country):
    transaction_date = _transaction_date_value(transaction)
    if transaction_date is None:
        return False
    today = _dispute_reference_date(country)
    cutoff = _country_policy_cutoff(country, reference_date=today)
    return cutoff <= transaction_date <= today


def _normalize_for_intent(value):
    return " ".join(str(value or "").lower().replace("’", "'").split())


def _is_case_history_request(message):
    normalized = _normalize_for_intent(message)
    return any(signal in normalized for signal in case_history_signals)


def _is_transaction_history_request(message):
    normalized = _normalize_for_intent(message)
    return any(signal in normalized for signal in transaction_history_signals)


def _is_human_escalation_request(message):
    normalized = _normalize_for_intent(message)
    if any(signal in normalized for signal in human_escalation_signals):
        return True
    return "humano" in normalized and any(
        word in normalized
        for word in ("manda", "mánd", "hablar", "escalar", "quiero")
    )


def _is_ambiguous_transaction_request(message):
    """Detect intentionally vague transaction requests that require clarification."""

    if _is_personal_dispute_message(message):
        return False
    normalized = _normalize_for_intent(message)
    return any(signal in normalized for signal in ambiguous_transaction_signals)


def _is_out_of_scope_banking_request(message):
    """Detect banking operations outside Hermes transaction-dispute scope."""

    normalized = _normalize_for_intent(message)

    # Dispute/transaction questions remain in scope even when they mention an
    # ATM withdrawal, transfer, card, or other transaction mechanism.
    if any(term in normalized for term in dispute_scope_terms):
        return False

    return any(signal in normalized for signal in out_of_scope_banking_signals)


def _out_of_scope_message(language):
    messages = {
        "en": (
            "Hermes only assists with disputed or unrecognized transactions "
            "and with your transaction or dispute records."
        ),
        "es": (
            "Hermes solo ayuda con transacciones disputadas o no reconocidas "
            "y con tus registros de transacciones o disputas."
        ),
        "pt": (
            "Hermes só ajuda com transações contestadas ou não reconhecidas "
            "e com seus registros de transações ou contestações."
        ),
    }
    return messages[language]


def _clarification_message(language):
    return {
        "en": "What is wrong with the transaction: do you not recognize it, is the amount incorrect, is it duplicated, or is there another issue?",
        "es": "¿Qué problema tiene la transacción: no la reconoces, el monto es incorrecto, está duplicada o se trata de otro problema?",
        "pt": "Qual é o problema com a transação: você não a reconhece, o valor está incorreto, está duplicada ou existe outro problema?",
    }[language]


def _safe_transaction_for_model(transaction):
    """Return only verified transaction fields accepted by the Worker model endpoint."""

    if not transaction:
        return {}
    fields = (
        "transaction_id",
        "transaction_type",
        "transaction_category",
        "amount_usd",
        "channel",
        "merchant_category",
        "transaction_status",
        "is_fraud",
        "fraud_score",
    )
    return {field: transaction.get(field) for field in fields}


def _build_handoff(customer_id, dispute, transaction, reason, evidence_ids):
    """Build a structured, verified handoff for human review."""

    return {
        "customer_request": reason,
        "verified_facts": {
            "customer_id": customer_id,
            "dispute_id": str(dispute.get("dispute_id") or ""),
            "transaction_id": transaction.get("transaction_id"),
            "transaction_date": transaction.get("transaction_date"),
            "product_id": transaction.get("product_id"),
            "merchant_name": transaction.get("merchant_name"),
            "amount": transaction.get("amount"),
            "currency": transaction.get("currency"),
            "channel": transaction.get("channel"),
            "transaction_status": transaction.get("transaction_status"),
        },
        "actions_taken": [
            "Customer identity was verified by Cognito.",
            "Transaction ownership was verified against RDS.",
            "A dispute record was created or an existing active dispute was reused.",
            "Human review was requested for the dispute.",
        ],
        "supporting_evidence_ids": list(evidence_ids or []),
        "unresolved_questions": [
            "Determine the final dispute outcome after reviewing the verified transaction and available evidence."
        ],
    }


def _extract_case_id(message):
    value = str(message or "")

    complaint_match = re.search(r"\bCMP-[A-Z0-9]+\b", value, flags=re.IGNORECASE)
    if complaint_match:
        return complaint_match.group(0).upper()

    dispute_match = re.search(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        value,
    )
    if dispute_match:
        return dispute_match.group(0).lower()

    return None


def _case_detail_message(case, language):
    if case is None:
        return {
            "en": "I could not find that case in your account.",
            "es": "No encontré ese caso en tu cuenta.",
            "pt": "Não encontrei esse caso na sua conta.",
        }[language]

    return {
        "en": "I found that case and displayed its details on the right.",
        "es": "Encontré ese caso y mostré sus detalles en el panel derecho.",
        "pt": "Encontrei esse caso e mostrei os detalhes no painel à direita.",
    }[language]


def _extract_iso_date_range(message):
    values = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", str(message or ""))
    parsed = []
    for value in values[:2]:
        try:
            parsed.append(date.fromisoformat(value))
        except ValueError:
            pass
    start_date = parsed[0] if parsed else None
    end_date = parsed[1] if len(parsed) > 1 else None
    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date
    return start_date, end_date


def _policy_context_message(country, language):
    """Build the deterministic country/date/time dispute-window explanation."""

    current_local = _country_local_now(country)
    policy = _country_policy(country)
    days = policy["days"]
    window_type = policy["type"]
    timestamp = current_local.strftime("%Y-%m-%d %H:%M")

    if window_type == "business_days":
        units = {
            "en": "business day" if days == 1 else "business days",
            "es": "día hábil" if days == 1 else "días hábiles",
            "pt": "dia útil" if days == 1 else "dias úteis",
        }
    elif window_type == "calendar_days":
        units = {
            "en": "calendar day" if days == 1 else "calendar days",
            "es": "día calendario" if days == 1 else "días calendario",
            "pt": "dia corrido" if days == 1 else "dias corridos",
        }
    else:
        raise RuntimeError(f"Unsupported dispute policy window type: {window_type}")

    messages = {
        "en": (
            f"As of {timestamp} local time, you are registered in {country}. "
            f"The maximum dispute period is {days} {units['en']}."
        ),
        "es": (
            f"A fecha de {timestamp}, hora local, estás registrado en {country}. "
            f"El plazo máximo para disputar es de {days} {units['es']}."
        ),
        "pt": (
            f"Em {timestamp}, horário local, você está registrado em {country}. "
            f"O prazo máximo para contestação é de {days} {units['pt']}."
        ),
    }

    if os.getenv("DEMO_MODE", "0").strip() == "1":
        reference_date = _dispute_reference_date(country)
        cutoff_date = _country_policy_cutoff(
            country,
            reference_date=reference_date,
        )
        demo_messages = {
            "en": (
                f" DEMO: to keep the prototype consistent with the available dataset period, "
                f"eligibility is evaluated using {reference_date.isoformat()} as the reference date, "
                f"with a demo threshold of {cutoff_date.isoformat()}."
            ),
            "es": (
                f" DEMO: para mantener el prototipo coherente con el período disponible del dataset, "
                f"la elegibilidad se evalúa usando {reference_date.isoformat()} como fecha de referencia, "
                f"con un umbral de demo de {cutoff_date.isoformat()}."
            ),
            "pt": (
                f" DEMO: para manter o protótipo coerente com o período disponível do dataset, "
                f"a elegibilidade é avaliada usando {reference_date.isoformat()} como data de referência, "
                f"com um limite de demonstração de {cutoff_date.isoformat()}."
            ),
        }
        messages[language] += demo_messages[language]

    return messages[language]


def _case_history_message(cases, language, country):
    policy_context = _policy_context_message(country, language)
    if not cases:
        detail = {
            "en": "I found no disputes or complaints still within that period.",
            "es": "No encontré disputas ni reclamos que sigan dentro de ese plazo.",
            "pt": "Não encontrei contestações ou reclamações que ainda estejam dentro desse prazo.",
        }[language]
    else:
        detail = {
            "en": f"I found {len(cases)} dispute/complaint record(s) still within that period and displayed them on the right.",
            "es": f"Encontré {len(cases)} disputa(s) o reclamo(s) que siguen dentro de ese plazo y los mostré en el panel derecho.",
            "pt": f"Encontrei {len(cases)} contestação(ões) ou reclamação(ões) que ainda estão dentro desse prazo e mostrei no painel à direita.",
        }[language]
    return f"{policy_context} {detail}"


def _transaction_history_message(transactions, language, country):
    policy_context = _policy_context_message(country, language)
    if not transactions:
        detail = {
            "en": "I found no transactions for your request within that allowed period.",
            "es": "No encontré transacciones para tu consulta dentro de ese plazo permitido.",
            "pt": "Não encontrei transações para sua consulta dentro desse prazo permitido.",
        }[language]
    else:
        detail = {
            "en": f"I found {len(transactions)} transaction(s) for your request within that allowed period and displayed them on the right.",
            "es": f"Encontré {len(transactions)} transacción(es) para tu consulta dentro de ese plazo permitido y las mostré en el panel derecho.",
            "pt": f"Encontrei {len(transactions)} transação(ões) para sua consulta dentro desse prazo permitido e mostrei no painel à direita.",
        }[language]
    return f"{policy_context} {detail}"


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
def transactions(customer_context=Depends(get_current_customer_context)):
    """Return only transactions that remain disputable today under the customer's country policy."""

    customer_id = customer_context["customer_id"]
    country = customer_context["country"]
    today = _dispute_reference_date(country)
    cutoff = _country_policy_cutoff(country, reference_date=today)
    return {
        "transactions": get_customer_transactions(
            customer_id,
            limit=100,
            start_date=cutoff,
            end_date=today,
        )
    }


@app.post("/disputes")
def create_dispute(payload=Body(...), customer_context=Depends(get_current_customer_context)):
    """Create one dispute after explicit transaction selection and verified inference."""

    customer_id = customer_context["customer_id"]
    country = customer_context["country"]
    transaction_id = payload.get("transaction_id", "").strip()
    reason = payload.get("reason", "").strip()
    language = _normalize_language(payload.get("language", "en"))
    interaction_id = payload.get("interaction_id", "").strip()
    evidence_ids = payload.get("evidence_ids", []) or []
    force_human_review = bool(payload.get("force_human_review", False))

    if not interaction_id:
        raise HTTPException(status_code=400, detail="interaction_id is required")

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

    reason_language = detect_language(reason, fallback=language)
    safe_reason = sanitize_text(reason, reason_language)

    try:
        transaction = get_customer_transaction(
            customer_id=customer_id,
            transaction_id=transaction_id,
        )
        if transaction is None:
            raise LookupError("Transaction does not belong to the authenticated customer")
        if not _transaction_is_currently_disputable(transaction, country):
            raise ValueError("Transaction is outside the configured dispute window for this country")

        segment = get_customer_segment(customer_id)

        if force_human_review:
            prediction = {
                "escalation_probability": None,
                "requires_human_review": True,
            }
        else:
            prediction = predict_escalation_worker(
                text=safe_reason,
                language=reason_language,
                country=country,
                segment=segment,
                transaction=_safe_transaction_for_model(transaction),
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
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.exception("Dispute creation failed")
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
    handoff = None
    if dispute["status"] == "ESCALATED":
        response = get_prompt_config()["ESCALATION_MESSAGE"][language]
        handoff = _build_handoff(
            customer_id=customer_id,
            dispute=dispute,
            transaction=transaction,
            reason=safe_reason,
            evidence_ids=evidence_ids,
        )

    return {
        "dispute": dispute,
        "response": response,
        "handoff": handoff,
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

    requested_case_id = _extract_case_id(message)
    if requested_case_id:
        if not customer_id:
            return {
                "response": None,
                "authentication_required": True,
                "personal_dispute": False,
                "needs_satisfaction_feedback": False,
                "needs_transaction_selection": False,
            }

        try:
            cutoff = _country_policy_cutoff(country, reference_date=_dispute_reference_date(country))
            case = get_customer_case(
                customer_id=customer_id,
                case_id=requested_case_id,
                cutoff_date=cutoff,
            )
        except Exception as error:
            logger.exception("Customer case-detail lookup failed")
            raise HTTPException(
                status_code=502,
                detail=get_prompt_config()["FAILURE_MESSAGE"][language],
            ) from error

        response = {
            "response": _case_detail_message(case, language),
            "personal_dispute": False,
            "retrieval_used": False,
            "needs_satisfaction_feedback": False,
            "needs_transaction_selection": False,
            "authentication_required": False,
        }
        if case is not None:
            response["case_detail"] = case
            linked_transaction_id = case.get("transaction_id")
            if linked_transaction_id:
                try:
                    linked_transaction = get_customer_transaction(
                        customer_id=customer_id,
                        transaction_id=linked_transaction_id,
                    )
                except Exception:
                    logger.exception("Linked transaction lookup failed")
                    linked_transaction = None
                if linked_transaction is not None:
                    response["linked_transaction"] = linked_transaction
        return response

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
            cutoff = _country_policy_cutoff(country, reference_date=_dispute_reference_date(country))
            cases = get_customer_case_history(
                customer_id=customer_id,
                limit=20,
                cutoff_date=cutoff,
            )
        except Exception as error:
            logger.exception("Customer case-history lookup failed")
            raise HTTPException(
                status_code=502,
                detail=get_prompt_config()["FAILURE_MESSAGE"][language],
            ) from error

        return {
            "response": _case_history_message(cases, language, country),
            "case_history": cases,
            "personal_dispute": False,
            "retrieval_used": False,
            "needs_satisfaction_feedback": False,
            "needs_transaction_selection": False,
            "authentication_required": False,
        }

    if _is_transaction_history_request(message):
        if not customer_id:
            return {
                "response": None,
                "authentication_required": True,
                "personal_dispute": False,
                "needs_satisfaction_feedback": False,
                "needs_transaction_selection": False,
            }

        start_date, end_date = _extract_iso_date_range(message)
        today = _dispute_reference_date(country)
        policy_cutoff = _country_policy_cutoff(country, reference_date=today)
        effective_start = max(filter(None, [start_date, policy_cutoff]))
        effective_end = min(filter(None, [end_date, today])) if end_date else today

        try:
            transactions = (
                get_customer_transactions(
                    customer_id=customer_id,
                    limit=100,
                    start_date=effective_start,
                    end_date=effective_end,
                )
                if effective_start <= effective_end
                else []
            )
        except Exception as error:
            logger.exception("Customer transaction-history lookup failed")
            raise HTTPException(
                status_code=502,
                detail=get_prompt_config()["FAILURE_MESSAGE"][language],
            ) from error

        return {
            "response": _transaction_history_message(transactions, language, country),
            "transaction_history": transactions,
            "personal_dispute": False,
            "retrieval_used": False,
            "needs_satisfaction_feedback": False,
            "needs_transaction_selection": False,
            "authentication_required": False,
        }

    if _is_human_escalation_request(message):
        if not customer_id:
            return {
                "response": None,
                "authentication_required": True,
                "personal_dispute": True,
                "human_escalation_requested": True,
                "needs_satisfaction_feedback": False,
                "needs_transaction_selection": False,
            }

        return {
            "response": None,
            "authentication_required": False,
            "personal_dispute": True,
            "human_escalation_requested": True,
            "retrieval_used": False,
            "needs_satisfaction_feedback": False,
            "needs_transaction_selection": True,
        }

    if _is_ambiguous_transaction_request(message):
        return {
            "response": _clarification_message(language),
            "clarification_required": True,
            "personal_dispute": False,
            "retrieval_used": False,
            "needs_satisfaction_feedback": False,
            "needs_transaction_selection": False,
            "authentication_required": False,
        }

    if _is_out_of_scope_banking_request(message):
        return {
            "response": _out_of_scope_message(language),
            "out_of_scope": True,
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
