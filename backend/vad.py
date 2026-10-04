from functools import lru_cache

from pysentimiento import create_analyzer


emotion_vad = {
    "anger": (-0.51, 0.59, 0.25),
    "disgust": (-0.60, 0.35, 0.11),
    "fear": (-0.62, 0.82, -0.43),
    "joy": (0.81, 0.51, 0.46),
    "sadness": (-0.63, -0.27, -0.33),
    "surprise": (0.40, 0.67, -0.13),
    "others": (0.00, 0.00, 0.00),
}


@lru_cache(maxsize=3)
def _get_emotion_analyzer(language):
    """Loads one local emotion analyzer.

    Parameters
    ----------
    language : str
        English, Spanish, or Portuguese language code.

    Returns
    -------
    object
        Cached pysentimiento emotion analyzer.
    """
    if language not in {"en", "es", "pt"}:
        language = "es"

    return create_analyzer(
        task="emotion",
        lang=language,
    )


def extract_vad(text, language="es"):
    """Converts local emotion probabilities into VAD scores.

    Parameters
    ----------
    text : str
        Sanitized customer text.
    language : str
        English, Spanish, or Portuguese language code.

    Returns
    -------
    dict
        Valence, arousal, and dominance values in the -1 to 1 range.
    """
    if not text or not text.strip():
        return {
            "valence": 0.0,
            "arousal": 0.0,
            "dominance": 0.0,
        }

    analyzer = _get_emotion_analyzer(language)
    result = analyzer.predict(text[:4000])
    probabilities = result.probas

    valence = 0.0
    arousal = 0.0
    dominance = 0.0
    total = 0.0

    for emotion, coordinates in emotion_vad.items():
        probability = float(probabilities.get(emotion, 0.0))
        valence += probability * coordinates[0]
        arousal += probability * coordinates[1]
        dominance += probability * coordinates[2]
        total += probability

    if total <= 0:
        return {
            "valence": 0.0,
            "arousal": 0.0,
            "dominance": 0.0,
        }

    return {
        "valence": max(-1.0, min(1.0, valence / total)),
        "arousal": max(-1.0, min(1.0, arousal / total)),
        "dominance": max(-1.0, min(1.0, dominance / total)),
    }
