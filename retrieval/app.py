from fastapi import Body, FastAPI, HTTPException

from retrieval.retrieval import search_similar_cases


app = FastAPI(
    title="Factored AI Retrieval",
    docs_url=None,
    redoc_url=None,
)


@app.get("/health")
def health():
    """Return retrieval service health status."""

    return {"status": "ok"}


@app.post("/internal/retrieval/search")
def internal_retrieval_search(payload=Body(...)):
    """Run country-aware E5 and FAISS similarity search."""

    text = payload.get("text", "").strip()
    country = payload.get("country", "").strip()
    k = min(max(int(payload.get("k", 5)), 1), 20)

    if not text:
        raise HTTPException(
            status_code=400,
            detail="text is required",
        )

    if not country:
        raise HTTPException(
            status_code=400,
            detail="country is required",
        )

    return {
        "matches": search_similar_cases(
            text=text,
            country=country,
            k=k,
        )
    }
