import csv
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path


vad_lexicon_path = Path(
    os.getenv(
        "VAD_LEXICON_PATH",
        "/opt/factored-ai/model_assets/vad_lexicon.tsv",
    )
)
token_pattern = re.compile(r"[^\W\d_]+", re.UNICODE)


def _normalize_token(token):
    """Normalize one token for VAD lexicon lookup."""

    return unicodedata.normalize("NFKC", token).lower().strip()


@lru_cache(maxsize=1)
def _load_lexicon():
    """Load the configured tab-separated VAD lexicon."""

    if not vad_lexicon_path.exists():
        raise RuntimeError(f"VAD lexicon not found: {vad_lexicon_path}")

    lexicon = {}

    with vad_lexicon_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")

        if not reader.fieldnames:
            raise RuntimeError("VAD lexicon has no header")

        names = {
            name.lower().strip(): name
            for name in reader.fieldnames
        }
        word_column = names.get("word") or names.get("term") or names.get("token")
        valence_column = names.get("valence")
        arousal_column = names.get("arousal")
        dominance_column = names.get("dominance")

        if not all([word_column, valence_column, arousal_column, dominance_column]):
            raise RuntimeError(
                "VAD lexicon must contain word/term, valence, arousal and dominance columns"
            )

        for row in reader:
            token = _normalize_token(row[word_column])

            if not token:
                continue

            try:
                lexicon[token] = (
                    float(row[valence_column]),
                    float(row[arousal_column]),
                    float(row[dominance_column]),
                )
            except (TypeError, ValueError):
                continue

    if not lexicon:
        raise RuntimeError("VAD lexicon contains no usable rows")

    return lexicon


def extract_vad(text):
    """Extract mean valence, arousal and dominance from sanitized text."""

    lexicon = _load_lexicon()
    tokens = [
        _normalize_token(token)
        for token in token_pattern.findall(text or "")
    ]
    matches = [
        lexicon[token]
        for token in tokens
        if token in lexicon
    ]

    if not matches:
        raise ValueError("No VAD lexicon terms matched the supplied text")

    count = len(matches)
    return {
        "valence": sum(item[0] for item in matches) / count,
        "arousal": sum(item[1] for item in matches) / count,
        "dominance": sum(item[2] for item in matches) / count,
    }
