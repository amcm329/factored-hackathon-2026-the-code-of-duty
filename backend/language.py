import os
from functools import lru_cache
from pathlib import Path
import fasttext
import requests


supported_languages = {"en", "es", "pt"}
model_url = os.getenv(
    "FASTTEXT_LANGUAGE_MODEL_URL",
    "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz",
)
model_path = Path(
    os.getenv(
        "FASTTEXT_LANGUAGE_MODEL_PATH",
        str(Path.home() / ".cache" / "factored-ai" / "lid.176.ftz"),
    )
)
minimum_confidence = float(
    os.getenv(
        "FASTTEXT_LANGUAGE_MIN_CONFIDENCE",
        "0.65",
    )
)


def _ensure_model_file():
    """Ensure the FastText language model exists locally.

    Parameters
    ----------
    None.

    Returns
    -------
    pathlib.Path
        Local FastText language model path.
    """
    if model_path.exists():
        return model_path

    model_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    temporary_path = model_path.with_suffix(model_path.suffix + ".tmp")
    response = requests.get(
        model_url,
        timeout=120,
    )
    response.raise_for_status()
    temporary_path.write_bytes(response.content)
    temporary_path.replace(model_path)

    return model_path


@lru_cache(maxsize=1)
def _load_model():
    """Load and cache the FastText language identification model.

    Parameters
    ----------
    None.

    Returns
    -------
    fasttext.FastText._FastText
        Loaded language identification model.
    """
    return fasttext.load_model(
        str(_ensure_model_file())
    )


def detect_language(text, fallback="en"):
    """Detect English, Spanish, or Portuguese from text.

    Parameters
    ----------
    text : str
        Text whose language is detected.
    fallback : str
        Language used when detection is unavailable or uncertain.

    Returns
    -------
    str
        Detected language code or the fallback language.
    """
    if fallback not in supported_languages:
        fallback = "en"

    normalized_text = " ".join(
        str(text or "").split()
    ).strip()

    if not normalized_text:
        return fallback

    try:
        labels, probabilities = _load_model().predict(
            normalized_text[:10000],
            k=1,
        )
    except Exception:
        return fallback

    detected_language = labels[0].replace(
        "__label__",
        "",
        1,
    )
    confidence = float(probabilities[0])

    if detected_language not in supported_languages:
        return fallback

    if confidence < minimum_confidence:
        return fallback

    return detected_language
