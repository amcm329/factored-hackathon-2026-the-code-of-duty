from fastapi import Body, FastAPI, HTTPException

from backend.model import generate_reply


app = FastAPI(
    title="Factored AI Backend",
    docs_url=None,
    redoc_url=None
)


@app.get("/health")
def health():
    """Return backend health status."""

    return {
        "status": "ok"
    }


@app.post("/chat")
def chat(payload=Body(...)):
    """Generate a response from the financial LLM."""

    message = payload.get("message", "").strip()
    language = payload.get("language", "en")
    history = payload.get("history", [])

    if not message:
        raise HTTPException(
            status_code=400,
            detail="message is required"
        )

    response = generate_reply(
        message=message,
        language=language,
        history=history
    )

    return {
        "response": response
    }
