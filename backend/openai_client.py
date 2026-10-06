import os

from openai import OpenAI

from backend.language import detect_language
from backend.privacy import sanitize_text
from backend.secrets import get_openai_api_key, get_prompt_config


model_id = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
client = OpenAI(
    api_key=get_openai_api_key(),
)


def generate_reply(message, language="en", history=None, evidence_context=None, similar_cases=None):
    """Generate a response using sanitized conversation and internal context.

    Parameters:
        message: Current user message.
        language: Response language code.
        history: Previous user and assistant messages.
        evidence_context: Sanitized evidence text.
        similar_cases: Sanitized historical complaint context.

    Returns:
        dict: Assistant text and total OpenAI token usage.
    """

    history = history or []
    evidence_context = evidence_context or []
    similar_cases = similar_cases or []

    prompt_config = get_prompt_config()
    language_names = prompt_config["ALLOWED_LANGUAGES"]
    instructions = (
        f'{prompt_config["SYSTEM_PROMPT"].strip()}\n\n'
        f'Respond in {language_names[language]} unless the user explicitly asks '
        'for another supported response language. '
        'Never ask the customer to type a full card number, account number, or product identifier. '
        'When an authenticated dispute needs a transaction, the customer must select it from verified backend records. '
        'If no verified transaction is linked to a historical complaint, do not invent a linkage and do not ask for card details. '
        'SCOPE BOUNDARY: Hermes only supports transaction disputes, unrecognized or unauthorized transaction questions, '
        'dispute processes, and viewing or explaining verified transaction/dispute records. '
        'ATM and cash-withdrawal transactions are valid dispute targets when they appear in the customer verified transaction records. '
        'Do not reject a dispute because the transaction type is a withdrawal. '
        'Do not provide general banking support for initiating transfers, loans, balances, account opening or closing, '
        'cards unrelated to a dispute, or other banking products. For an out-of-scope banking request, reply briefly that Hermes '
        'only supports disputed or unrecognized transactions and transaction/dispute records. Do not provide generic instructions '
        'for completing the out-of-scope banking operation.'
    )

    input_messages = []

    for item in history[-10:]:
        role = item.get("role")
        content = item.get("content", "")

        if role in {"user", "assistant"} and content:
            history_language = detect_language(
                content,
                fallback=language,
            )
            input_messages.append(
                {
                    "role": role,
                    "content": sanitize_text(
                        content,
                        history_language,
                    ),
                }
            )

    if evidence_context:
        safe_evidence = [
            f"EVIDENCE_{index}:\n{text}"
            for index, text in enumerate(evidence_context, start=1)
        ]
        input_messages.append(
            {
                "role": "user",
                "content": (
                    "Sanitized supporting evidence for this case:\n\n"
                    + "\n\n".join(safe_evidence)
                ),
            }
        )

    if similar_cases:
        case_blocks = []

        for index, case in enumerate(similar_cases, start=1):
            case_blocks.append(
                "\n".join(
                    [
                        f"HISTORICAL_CASE_{index}:",
                        f"similarity={case.get('score', 0.0):.4f}",
                        f"category={case.get('category', '')}",
                        f"subcategory={case.get('subcategory', '')}",
                        f"priority={case.get('priority', '')}",
                        f"status={case.get('status', '')}",
                        f"description={case.get('description', '')}",
                        f"resolution={case.get('resolution', '')}",
                    ]
                )
            )

        input_messages.append(
            {
                "role": "user",
                "content": (
                    "Sanitized similar historical cases found internally. "
                    "Use them only as reference patterns and do not assume the current case is identical. "
                    "Based only on patterns actually supported by their descriptions and resolutions, "
                    "give the customer a concise explanation of plausible reasons for the transaction or issue "
                    "and one practical verification step. "
                    "Do not negotiate, promise reimbursement, claim that an explanation is confirmed, "
                    "or invent causes that are not supported by the retrieved cases. "
                    "Do not mention FAISS, retrieval, historical cases, internal systems, similarity scores, "
                    "or other customers. Present the explanation naturally as banking customer-service guidance.\n\n"
                    + "\n\n".join(case_blocks)
                ),
            }
        )

    input_messages.append(
        {
            "role": "user",
            "content": message,
        }
    )

    response = client.responses.create(
        model=model_id,
        instructions=instructions,
        input=input_messages,
        store=False,
    )

    usage = getattr(response, "usage", None)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)

    return {
        "response": response.output_text.strip(),
        "total_tokens": total_tokens,
    }
