import os

from openai import OpenAI

from backend.privacy import sanitize_text
from backend.secrets import get_openai_api_key

model_id = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

client = OpenAI(
    api_key=get_openai_api_key(),
)


def generate_reply(
    message,
    language="en",
    history=None,
    evidence_context=None,
    similar_cases=None,
):
    """Generate a response using sanitized conversation and evidence context."""

    if history is None:
        history = []

    if evidence_context is None:
        evidence_context = []

    if similar_cases is None:
        similar_cases = []

    language_names = {
        "en": "English",
        "es": "Spanish",
        "pt": "Portuguese",
    }

    language_name = language_names.get(language, "English")

    instructions = (
        "You are a banking customer-service assistant. "
        "Understand the user's intent and ambiguity, ask useful follow-up questions, "
        "and answer clearly. "
        f"Respond in {language_name}. "
        "Never invent customer records, transaction facts, eligibility rules, "
        "or completed actions. "
        "Treat references such as TRANSACTION_1, EVIDENCE_1 and HISTORICAL_CASE_1 "
        "as opaque aliases."
    )

    input_messages = []

    for item in history[-10:]:
        role = item.get("role")
        content = item.get("content", "")

        if role in {"user", "assistant"} and content:
            input_messages.append(
                {
                    "role": role,
                    "content": sanitize_text(content, language),
                }
            )

    if evidence_context:
        safe_evidence = []

        for index, text in enumerate(evidence_context, start=1):
            safe_evidence.append(
                f"EVIDENCE_{index}:
{text}"
            )

        input_messages.append(
            {
                "role": "user",
                "content": (
                    "Sanitized supporting evidence for this case:

"
                    + "

".join(safe_evidence)
                ),
            }
        )

    if similar_cases:
        case_lines = []

        for index, match in enumerate(similar_cases, start=1):
            case_lines.append(
                f"HISTORICAL_CASE_{index}: similarity={match['score']:.4f}"
            )

        input_messages.append(
            {
                "role": "user",
                "content": (
                    "Similar historical cases were found internally. "
                    "Do not infer facts that are not provided.
"
                    + "
".join(case_lines)
                ),
            }
        )

    input_messages.append(
        {
            "role": "user",
            "content": sanitize_text(message, language),
        }
    )

    response = client.responses.create(
        model=model_id,
        instructions=instructions,
        input=input_messages,
        store=False,
    )

    return response.output_text.strip()